import html
import os
import tarfile
import time
import traceback
import gc
import ftplib
import time
import sys

import iso8601

import utils
from utils import printc
from config import Config
from online import OnlineApiClient, OnlineApiError
from exceptions import CriticalError

VERSION = "2.1.0"


try:
    # Here's a cute birb (oiseau=birb in french)
    printc("""              ___
             (  ">
              )(
             // )
      jgs --//""--
          -/------""", utils.BColors.YELLOW)
    printc(" " * 7 + "oiseau @{}\n".format(VERSION), utils.BColors.YELLOW + utils.BColors.BOLD)

    # Load config
    config = Config()

    # Always run API checks
    # Check online.net api token
    if config.is_c14:
        client = OnlineApiClient(config["ONLINE_API_KEY"])
        logged_in = client.auth_valid()
        if not logged_in:
            raise CriticalError("Could not log in, check your online.net API key")

        # List all archives in all safes
        archives = client.request("api/v1/storage/c14/archive")
        if not archives:
            raise CriticalError("No C14 archives found")

    # Continue only if temp folder is big enough
    total_size = sum(os.path.getsize(os.path.join("temp", f)) for f in os.listdir("temp/") if os.path.isfile(os.path.join("temp", f)))
    if total_size < 500 * 1024 * 1024:
        printc(f"* Temp folder is too small ({total_size / 1024 / 1024} MB). Aborting.", utils.BColors.YELLOW)
        exit(0)

    # Filter only desired C14 buckets by name and sort them by creation date (most recent first)
    if config.is_c14:
        sync_archives = sorted(
            [
                {
                    **x,
                    "unix_creation_date": int(time.mktime(iso8601.parse_date(x["creation_date"]).timetuple()))
                } for x in archives if x["name"].lower() == config["C14_SYNC_NAME"]
            ],
            key=lambda x: x["unix_creation_date"],
            reverse=True
        )
        if not sync_archives:
            raise CriticalError("No C14 archives matching given name found!")

        # Make sure that ALL sync archives are 'active', if there's something 'busy' or 'deleting', we want
        # to wait for these pending operation to finish before extracting our archive again
        if not all(x["status"] == "active" for x in sync_archives):
            raise CriticalError(
                "Found sync archive(s), but not all of them are 'active'. "
                "There's probably an (un)archive operation in progress. Retry later"
            )


        # Delete old sync archives if needed
        if len(sync_archives) > 1:
            # Paranoid
            # assert all(sync_archives[0]["unix_creation_date"] > x["unix_creation_date"] for x in sync_archives[1:])

            # In sync_archives[0] there's the most recent bucket (that we want to keep)
            # Other archives are outdated copies that we don't need anymore
            for outdated_archive in sync_archives[1:]:
                printc("* Archive {} should be deleted".format(outdated_archive["uuid_ref"]), utils.BColors.YELLOW)
                try:
                    # TODO: Enable once we are sure online.net rearchive works
                    # client.request(
                    #    handler=outdated_archive["$ref"],
                    #    method="DELETE"
                    # )
                    utils.telegram_notify(
                        "Archive {} should be deleted. "
                        "This will be automatic once we figure out whether "
                        "online.net's 'automatic rearchive' feature is broken or not.".format(
                            outdated_archive["uuid_ref"]
                        ),
                        prefix=utils.TelegramPrefixes.NORMAL
                    )
                except OnlineApiError as e:
                    if e.request.status_code == 409:
                        # Delete action already pending, pretend nothing happend
                        pass

        # Get wanted sync archive (the most recent one)
        sync_archive = sync_archives[0]

        # Get temporary bucket from sync archive
        temp_bucket = None
        try:
            temp_bucket = client.request("{}/bucket".format(sync_archive["$ref"]))
        except OnlineApiError as e:
            if e.request.status_code != 404:
                # Other error. 404 if there's no temporary space open
                raise e

        if temp_bucket is None:
            # This archive is archived!
            printc(
                "* Temporary bucket for {} not found, unarchiving it.".format(sync_archive["uuid_ref"]),
                utils.BColors.YELLOW
            )

            # Get the location (first available)
            locations = client.request("{}/location".format(sync_archive["$ref"]))
            if not locations:
                raise CriticalError("No locations found for bucket {}".format(sync_archive["uuid_ref"]))
            printc(
                "* Using location {} (0/{})".format(locations[0]["uuid_ref"], len(locations) - 1),
                utils.BColors.BLUE
            )

            # Get SSH key(s)
            # ssh_keys = client.request("api/v1/user/key/ssh")
            # valid_ssh_keys = [
            #     x["uuid_ref"] for x in ssh_keys if x["description"].lower() in [
            #         y.lower() for y in config["C14_ALLOWED_SSH_KEYS"]
            #     ]
            # ]
            # printc(
            #     "* Using SSH keys: {}".format(valid_ssh_keys),
            #     utils.BColors.BLUE
            # )
            # additional = {}
            # if valid_ssh_keys:
            #     additional["ssh_keys"] = valid_ssh_keys

            # Unarchive request
            additional = {}
            try:
                client.request(
                    handler="{}/unarchive".format(sync_archive["$ref"]),
                    method="POST",
                    json={
                        **{
                            "location_id": locations[0]["uuid_ref"],
                            "protocols": ["ssh", "ftp"],
                            "rearchive": True
                        },
                        **additional
                    }
                )
                m = "Started unarchiving {}".format(sync_archive["uuid_ref"])
                printc("* {}".format(m), utils.BColors.GREEN)
                utils.telegram_notify(m, prefix=utils.TelegramPrefixes.NORMAL)

                # Exit because we don't have a temporary bucket yet
                sys.exit()
            except OnlineApiError as e:
                if e.request.status_code == 409:
                    # Operation already requested
                    raise CriticalError(
                        "An unarchive operation for {} has already been requested".format(sync_archive["uuid_ref"])
                    )
                else:
                    # Other error
                    raise e

        # C14 is looking good, get SSH credentials
        # This archive has an open temporary storage box
        printc("* Temporary bucket {} found".format(temp_bucket["uuid_ref"]), utils.BColors.BLUE)

        # Get FTP credentials
        bucket_info = client.request(handler=sync_archive["$ref"])
        ftp_user = None
        ftp_password = None
        ftp_host = None
        ftp_port = None
        for credentials in bucket_info["bucket"]["credentials"]:
            if credentials["protocol"] == "ftp":
                ftp_user = credentials["login"]
                ftp_password = credentials["password"]
                prefix = f"ftp://{ftp_user}@"
                assert credentials["uri"].startswith(prefix)
                uri_parts = credentials["uri"][len(prefix):].split(":")
                assert len(uri_parts) == 2
                ftp_host = uri_parts[0]
                ftp_port = int(uri_parts[1])
        if any(x is None for x in (ftp_user, ftp_host, ftp_port, ftp_password)):
            raise CriticalError("Could not determine ftp credentials")
        printc("* Found FTP credentials", utils.BColors.BLUE)

    # Download tar gz index
    printc("* Retreiving tar gz index", utils.BColors.BLUE)
    if os.path.isfile("/tmp/c14_index.txt"):
        os.remove("/tmp/c14_index.txt")
    if config.is_c14:        
        try:
            session = ftplib.FTP()
            session.connect(ftp_host, ftp_port)
            session.login(ftp_user, ftp_password)
            with open(f"/tmp/c14_index.txt", "wb") as f:
                session.retrbinary(f"RETR c14_index.txt", f.write)
        finally:
            session.quit()
    else:
        # rclone copy 1580469306_replays_575.tar.gz gdrive:Bunker --progress
        utils.rclone_copy(f"{config['RCLONE_REMOTE']}/c14_index.txt", "/tmp")
        if not os.path.isfile("/tmp/c14_index.txt"):
            raise CriticalError("Cannot download c14_index with rclone. Local file not found.")

    # Determine new archive id (last one in file)
    old_archive_id = -1
    with open("/tmp/c14_index.txt", "r") as f:
        for line in f:
            # Skip empty lines
            if not line.strip():
                continue
            parts = line.split("\t")
            old_archive_id = int(parts[0])

    # Empty file
    if old_archive_id < 0:
        raise CriticalError("Could not determine the previous archive id from the tar gz index")

    # Determine new archive and max replay id
    new_archive_id = old_archive_id + 1
    replay_ids = []

    # Store all replay ids
    for file in os.listdir("temp/"):
        if not os.path.isfile(os.path.join("temp", file)) or not file.startswith("replay_") or not file.endswith(".osr"):
            continue
        replay_id = int(file[len("replay_"):-len(".osr")])
        replay_ids.append(replay_id)
    if not replay_ids:
        raise CriticalError("No replays?")

    # Get the max
    max_replay_id = max(replay_ids)

    # Update tmp c14 index with new archive id and max replay
    with open("/tmp/c14_index.txt", "a") as f:
        f.write(f"{new_archive_id}\t{max_replay_id}\n")
    printc(f"* New archive id: {new_archive_id}, max replay id: {max_replay_id}", utils.BColors.BLUE)

    # Hopefully the gc will take care of replay_ids
    del replay_ids
    gc.collect()

    # Create .tar.gz with all replays
    printc(f"* Creating tar gz file", utils.BColors.BLUE)
    the_time = int(time.time())
    tar_gz_name = f"{the_time}_replays_{new_archive_id}.tar.gz"
    with tarfile.open(tar_gz_name, "w:gz") as tar:
        for t_file in os.listdir("temp/"):
            tar.add(os.path.join("temp", t_file), t_file)

    # Upload
    printc(f"* {tar_gz_name} created. Now uploading.", utils.BColors.BLUE)
    if config.is_c14:
        # C14
        try:
            session = ftplib.FTP()
            session.connect(ftp_host, ftp_port)
            session.login(ftp_user, ftp_password)

            # Upload .tar.gz
            with open(tar_gz_name, "rb") as f:
                session.storbinary(f"STOR {tar_gz_name}", f)

            # Upload c14 index
            with open("/tmp/c14_index.txt", "rb") as f:
                session.storbinary(f"STOR c14_index.txt", f)
                session.storbinary(f"STOR {the_time}_c14_index.txt", f)
        finally:
            session.quit()

        # TODO: Enable once we are sure online.net rearchive works
        # printc(f"* Cleanup time! Deleting the tar gz file", utils.BColors.BLUE)
        # os.remove(tar_gz_name)
    else:
        # rclone
        utils.rclone_copy(tar_gz_name, config["RCLONE_REMOTE"], progress=True)
        utils.rclone_copy("/tmp/c14_index.txt", config["RCLONE_REMOTE"])

    printc(f"* Emptying the temp folder as well", utils.BColors.BLUE)
    # TODO: Delete only files in the replay ids array, so we avoid deleting unsynced files if new files are synced while taking the backup
    for file in os.listdir("temp/"):
        os.remove(os.path.join("temp", file))

    printc(f"* Deleting temp tar gz index", utils.BColors.BLUE)
    os.rename("/tmp/c14_index.txt", f"{the_time}_c14_index.txt")
    # TODO: Remove line above and uncomment the line below once we are sure onlime.net rearchive works
    # os.remove("/tmp/c14_index.txt")

    # Finally done
    utils.printc("* All done!", utils.BColors.GREEN)
    utils.telegram_notify(f"A new chunked backup has been made and uploaded to C14 ({tar_gz_name})")
    # TODO: Remove once we are sure online.net rearchive works
    utils.telegram_notify(
        "The .tar.gz and index file have not been deleted from local disk as a precaution in case online.net's rearchive does not work.",
        prefix=utils.TelegramPrefixes.ALERT
    )
except CriticalError as e:
    printc("# {}".format(e.message), utils.BColors.RED + utils.BColors.BOLD)
    utils.telegram_notify(
        "<b>Critical error during backup.</b>\n\n<code>{}</code>".format(e.message),
        prefix=utils.TelegramPrefixes.ERROR
    )
    exit(-1)
except OnlineApiError as e:
    printc("# Online API Error", utils.BColors.RED)
    printc("{}: {}".format(e.request.status_code, e.request.text), utils.BColors.RED)
    utils.telegram_notify(
        "<b>Online API Error during backup:</b>\n\n<code>{}: {}</code>".format(e.request.status_code, html.escape(e.request.text)),
        prefix=utils.TelegramPrefixes.ERROR
    )
except Exception as e:
    printc("# Unknown error while backing up ({})".format(str(e)), utils.BColors.RED)
    tb = traceback.format_exc()
    utils.telegram_notify(
        "<b>Unhandled exception during backup.</b>\n\n<code>{}</code>".format(html.escape(tb)),
        prefix=utils.TelegramPrefixes.ERROR
    )

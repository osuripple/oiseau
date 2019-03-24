import html
import os
import tarfile
import time
import traceback

import iso8601

import utils
from utils import printc
from config import Config
from online import OnlineApiClient, OnlineApiError

VERSION = "1.0.0"


class CriticalError(Exception):
    def __init__(self, message):
        self.message = message

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

    # Check online.net api token
    client = OnlineApiClient(config["ONLINE_API_KEY"])
    logged_in = client.auth_valid()
    if not logged_in:
        raise CriticalError("Could not log in, check your online.net API key")

    # List all archives in all safes
    archives = client.request("api/v1/storage/c14/archive")
    if not archives:
        raise CriticalError("No C14 archives found")

    # Filter only desired C14 buckets by name and sort them by creation date (most recent first)
    sync_archives = sorted(
        [x for x in archives if x["name"].lower() == config["C14_SYNC_NAME"]],
        key=lambda x: int(time.mktime(iso8601.parse_date(x["creation_date"]).timetuple())),
        reverse=True
    )
    if not sync_archives:
        raise CriticalError("No C14 archives matching given name found!")

    # Make sure that ALL sync archives are 'active', if there's something 'busy' or 'deleting', we want
    # to wait for these pending operation to finish before extracting our archive again
    for archive in sync_archives:
        if archive["status"] != "active":
            raise CriticalError(
                "Found sync archive(s), but not all of them are 'active' (found '{}'), retry later".format(
                    archive["status"]
                )
            )

    # Delete old sync archives if needed
    if len(sync_archives) > 1:
        # In sync_archives[0] there's the most recent bucket (that we want to keep)
        # Other archives are outdated copies that we don't need anymore
        for outdated_archive in sync_archives[1:]:
            printc("* Deleting outdated archive {}...".format(outdated_archive["uuid_ref"]), utils.BColors.BLUE)
            try:
                client.request(
                    handler=outdated_archive["$ref"],
                    method="DELETE"
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
            "* Temporary bucket for {} not found, creating one...".format(sync_archive["uuid_ref"]),
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
        ssh_keys = client.request("api/v1/user/key/ssh")
        valid_ssh_keys = [
            x["uuid_ref"] for x in ssh_keys if x["description"].lower() in [
                y.lower() for y in config["C14_ALLOWED_SSH_KEYS"]
            ]
        ]
        printc(
            "* Using SSH keys: {}".format(valid_ssh_keys),
            utils.BColors.BLUE
        )
        if not valid_ssh_keys:
            raise CriticalError("No valid SSH keys found")

        # Unarchive request
        try:
            client.request(
                handler="{}/unarchive".format(sync_archive["$ref"]),
                method="POST",
                json={
                    "location_id": locations[0]["uuid_ref"],
                    "protocols": ["ssh", "ftp"],
                    "ssh_keys": valid_ssh_keys,
                }
            )
        except OnlineApiError as e:
            if e.request.status_code == 409:
                # Operation already requested
                raise CriticalError(
                    "An unarchive operation for {} has already been requested".format(sync_archive["uuid_ref"])
                )
            else:
                # Other error
                raise e

        raise CriticalError("Started unarchiving {}".format(sync_archive["uuid_ref"]))

    # C14 is looking good, get SSH credentials
    # This archive has an open temporary storage box
    printc("* Temporary bucket {} found".format(temp_bucket["uuid_ref"]), utils.BColors.BLUE)

    # Get SSH credentials
    ssh_uri = None
    for credential in temp_bucket["credentials"]:
        if credential["protocol"] == "ssh":
            ssh_uri = credential["uri"]

    # SSH not configured
    if ssh_uri is None:
        raise CriticalError("SSH is not configured for bucket {}!".format(temp_bucket["uuid_ref"]))

    # Separate SSH remote from port
    try:
        ssh_remote, ssh_port = ssh_uri.lstrip("ssh://").split(":", 1)
    except ValueError:
        raise CriticalError("Invalid SSH uri ({})".format(ssh_uri))

    # Append folder (/buffer)
    ssh_remote += ":/buffer"
    printc("* Using SSH remote {} (port {})\n".format(ssh_remote, ssh_port), utils.BColors.BLUE)

    # We have everything we need from C14, start syncing
    # Sync replays, avatars, screenshots and profile backgrounds
    latest_sync = "Never"
    utils.call_process(utils.scp_download_cmd(
        "{}/latest_sync.txt".format(ssh_remote), ssh_port, "tmp/latest_sync.txt",
        key_location=Config()["SSH_KEY_LOCATION"])
    )
    if not os.path.isfile("tmp/latest_sync.txt"):
        utils.warn("Cannot find latest_sync on remote endpoint!")
    else:
        with open("tmp/latest_sync.txt") as f:
            latest_sync = f.read()
        os.remove("tmp/latest_sync.txt")

    telegram_status_message = utils.TelegramStatusMessage(latest_sync)
    done = {"replays": False, "avatars": False, "screenshots": False, "profile_backgrounds": False, "database": False}
    for d in (x.upper() for x in done.keys() if x != "database"):
        if not config["SYNC_{}".format(d)]:
            printc("* {} syncing disabled".format(d), utils.BColors.YELLOW)
            continue

        rsync_command = utils.rsync_upload_cmd(
            config["{}_FOLDER".format(d)], ssh_remote, ssh_port, key_location=Config()["SSH_KEY_LOCATION"]
        )
        printc("* Syncing {}".format(d), utils.BColors.BLUE)
        exit_code = utils.call_process(rsync_command)
        if exit_code != 0:
            raise CriticalError("Something went wrong while syncing {}! (exit code: {})".format(d, exit_code))
        utils.sync_done(d, telegram_status_message)

    if config["SYNC_DATABASE"]:
        # Dump database to tmp/db.sql
        database_file = "tmp/db.sql"
        archive_file = "tmp/db.tar.gz"
        printc("* Dumping database...", utils.BColors.BLUE)
        exit_code = utils.call_process(
            """mysqldump -u "{username}" "-p{password}" "{name}" > {output}""".format(
                username=config["DB_USERNAME"],
                password=config["DB_PASSWORD"],
                name=config["DB_NAME"],
                output=database_file
            )
        )
        if exit_code != 0:
            raise CriticalError("Something went wrong while dumping the database! (exit code: {})".format(exit_code))

        # Compress the database
        if Config()["COMPRESS_DATABASE"]:
            printc("* Compressing database", utils.BColors.BLUE)
            with tarfile.open(archive_file, "w:gz") as tar:
                tar.add(database_file, arcname=os.path.basename(archive_file))
            database_file = archive_file
        else:
            printc("* The database won't be compressed", utils.BColors.BLUE)

        # Sync database
        printc("* Syncing database ({})...".format(database_file), utils.BColors.BLUE)
        exit_code = utils.call_process(
            utils.rsync_upload_cmd(database_file, ssh_remote, ssh_port, key_location=Config()["SSH_KEY_LOCATION"])
        )
        if exit_code != 0:
            raise CriticalError("Something went wrong while syncing the database! (exit code: {})".format(exit_code))
        utils.sync_done("database", telegram_status_message)

        # Delete temp db dump
        printc("* Deleting temporary database dump...", utils.BColors.BLUE)
        os.remove("tmp/db.sql")
        if os.path.isfile(archive_file):
            os.remove(archive_file)

    # Write latest_sync.txt and sync it
    latest_sync = time.strftime('%x %X %Z')
    printc("\n* Updating latest sync to {}".format(latest_sync), utils.BColors.BLUE)
    with open("latest_sync.txt", "w+") as f:
        f.write(latest_sync)
    exit_code = utils.call_process(
        utils.rsync_upload_cmd("latest_sync.txt", ssh_remote, ssh_port, key_location=Config()["SSH_KEY_LOCATION"])
    )
    if exit_code != 0:
        raise CriticalError(
            "Something went wrong while syncing the latest sync date! (exit code: {})".format(exit_code)
        )

    # Finally done
    utils.printc("* All done!", utils.BColors.GREEN)
    telegram_status_message.latest_sync = latest_sync
    utils.sync_done(status_message=telegram_status_message)
except CriticalError as e:
    printc("# {}".format(e.message), utils.BColors.RED + utils.BColors.BOLD)
    utils.telegram_notify(
        "<b>Critical error during backup.</b>\n\n<code>{}</code>".format(e.message),
        prefix=utils.TelegramPrefixes.ERROR
    )
    exit(-1)
except Exception as e:
    printc("# Unknown error while backing up ({})".format(str(e)), utils.BColors.RED)
    tb = traceback.format_exc()
    utils.telegram_notify(
        "<b>Unhandled exception during backup.</b>\n\n<code>{}</code>".format(html.escape(tb)),
        prefix=utils.TelegramPrefixes.ERROR
    )

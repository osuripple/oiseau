import subprocess

import requests

from config import Config


def rsync_upload_cmd(source, dest, port):
    return """rsync -e "ssh -p {port} -oStrictHostKeyChecking=no" -azvP "{source}" "{dest}" """.format(
        port=port,
        source=source,
        dest=dest
    )


def scp_download_cmd(source, port, local_file, key_location="~/.ssh/id_rsa.pub"):
    return """scp -P {port} -i {key_location} {source} {local_file}""".format(
        port=port,
        source=source,
        key_location=key_location,
        local_file=local_file
    )


def call_process(command):
    process = subprocess.Popen(
        command,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Print rsync output to console
    while True:
        output_line = process.stdout.readline().decode("utf-8")
        if not output_line:
            break
        print(output_line)

    # Wait for the process to exit and return the exit code
    return process.wait()


class BColors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def printc(s, c):
    print("{}{}{}".format(c, s, BColors.ENDC))


class TelegramPrefixes:
    NORMAL = "🐦"
    ERROR = NORMAL + "💣"
    ALERT = NORMAL + "⚠️"
    SUCCESS = NORMAL + "👌"


def warn(message, telegram=True):
    printc("* {}".format(message), BColors.YELLOW)
    if telegram:
        telegram_notify("<b>Warning</b>\n\n<code>{}</code>".format(message), prefix=TelegramPrefixes.ALERT)


def telegram_api_call(method, data, token=None):
    if not Config()["TELEGRAM_TOKEN"]:
        return
    if token is None:
        token = Config()["TELEGRAM_TOKEN"]
    return requests.post("https://api.telegram.org/bot{}/{}".format(token, method), data=data)


def telegram_notify(message, chat_id=None, parse_mode="html", prefix=TelegramPrefixes.NORMAL):
    if chat_id is None:
        chat_id = Config()["TELEGRAM_CHAT_ID"]
    return telegram_api_call("sendMessage", {
        "chat_id": chat_id,
        "text": "{} {}".format(prefix, message),
        "parse_mode": parse_mode
    })


def telegram_status_message(
    replays=False, avatars=False, screenshots=False, profile_backgrounds=False,
    database=False, latest_sync=None, done=False
):
    return (TelegramPrefixes.NORMAL if not done else TelegramPrefixes.SUCCESS) + \
        "<b>C14 backup {}</b>\n\n".format("done!" if done else "in progress") + "\n".join(
        ("✅" if x else "🕐" if not x and Config()["SYNC_{}".format(ck)] else "❌") +
        " " +
        ck.lower().replace("_", " ").capitalize() for x, ck in zip(
            (replays, avatars, screenshots, profile_backgrounds, database),
            ("REPLAYS", "AVATARS", "SCREENSHOTS", "PROFILE_BACKGROUNDS", "DATABASE")
        )
    ) + "\n\nLatest sync: <code>{}</code>".format(latest_sync if not None else "Never")


def sync_done(done_dict, latest_sync, telegram_message_id=None, done=False, what=None):
    if what is not None:
        done_dict[what.lower()] = True
        printc("* Done syncing {}!\n".format(what), BColors.GREEN)
    if done:
        printc("* All done!\n", BColors.GREEN)
    if telegram_message_id is not None:
        telegram_api_call("editMessageText", {
            "chat_id": Config()["TELEGRAM_CHAT_ID"],
            "message_id": telegram_message_id,
            "text": telegram_status_message(latest_sync=latest_sync, **done_dict, done=done),
            "parse_mode": "html"
        })

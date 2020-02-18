import html
import subprocess
from typing import Callable, Any

import requests

from config import Config
from exceptions import CriticalError

def rclone_copy_cmd(source_file: str, dest_file: str, *, progress: bool = False) -> str:
    return f"""rclone copy "{source_file}" "{dest_file}" {'--progress' if progress else ''}"""


def rsync_upload_cmd(source, dest, port, key_location="~/.ssh/id_rsa.pub"):
    return """rsync -e "ssh -p {port} -oStrictHostKeyChecking=no -i {key}" -azvP "{source}" "{dest}" """.format(
        port=port,
        source=source,
        dest=dest,
        key=key_location
    )


def scp_download_cmd(source, port, local_file, key_location="~/.ssh/id_rsa.pub"):
    return """scp -P {port} -i {key_location} {source} {local_file}""".format(
        port=port,
        source=source,
        key_location=key_location,
        local_file=local_file
    )


def call_process(command: str) -> int:
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
        telegram_notify("<b>Warning</b>\n\n<code>{}</code>".format(html.escape(message)), prefix=TelegramPrefixes.ALERT)


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


class TelegramStatusMessage:
    def __init__(self, latest_sync):
        self.done_what = {k: False for k in ("replays", "avatars", "screenshots", "profile_backgrounds", "database")}
        self.latest_sync = latest_sync
        telegram_response = telegram_notify(self.telegram_message, prefix="")
        self.telegram_message_id = None
        if telegram_response is not None and telegram_response.status_code == 200:
            json_response = telegram_response.json()
            if json_response.get("ok", False):
                self.telegram_message_id = json_response.get("result", {}).get("message_id", None)

    @property
    def done(self):
        return all(not Config()["SYNC_{}".format(k.upper())] or v for k, v in self.done_what.items())

    @property
    def telegram_message(self):
        return (TelegramPrefixes.NORMAL if not self.done else TelegramPrefixes.SUCCESS) + \
               "<b>C14 backup {}</b>\n\n".format("done!" if self.done else "in progress") + "\n".join(
            ("✅" if x else "🕐" if not x and Config()["SYNC_{}".format(ck.upper())] else "❌") +
            " " +
            ck.replace("_", " ").capitalize() for ck, x in self.done_what.items()
        ) + "\n\nLatest sync: <code>{}</code>".format(self.latest_sync if not None else "Never")

    def update_telegram_message(self):
        if self.telegram_message_id is not None:
            telegram_api_call("editMessageText", {
                "chat_id": Config()["TELEGRAM_CHAT_ID"],
                "message_id": self.telegram_message_id,
                "text": self.telegram_message,
                "parse_mode": "html"
            })


def sync_done(what=None, status_message=None):
    if what is not None:
        status_message.done_what[what.lower()] = True
        printc("* Done syncing {}!\n".format(what), BColors.GREEN)
    if status_message is not None:
        status_message.update_telegram_message()


def must_success(f: Callable[[], int], success: Callable[[int], bool] = lambda x: x == 0) -> Any:
    r = f()
    if not success(r):
        raise CriticalError("Error: got {r}")
    return r

def rclone_copy(source: str, dest: str, *, progress: bool = False) -> Any:
    return must_success(lambda: call_process(rclone_copy_cmd(source, dest, progress=progress)))

import subprocess

import progressbar
import time


def rsync_cmd(source, dest, port):
    return """rsync -e "ssh -p {port} -oStrictHostKeyChecking=no" -azvP "{source}" "{dest}" """.format(
        port=port,
        source=source,
        dest=dest
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

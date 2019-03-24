# oiseau
## Ripple's data syncing and backup system using online.net's C14

### What's this?
This is a replacement for [icebirb](https://zxq.co/ripple/icebirb), our old sync and backup system. Recently we've switched to online.net's [C14](https://www.online.net/en/c14) cold storage solution and icebirb doesn't work really well with it, that's why we've replaced it with oiseau.

## How it works
This script checks if there's an open temporary space for our sync storage among our C14 safes, using online.net's API. If there's one, then it starts uploading data to it using rsync, if not it asks online.net to unarchive the sync storage to the temporary space and waits until the operation is completed. After 7 days, the temporary space is automatically archived by online.net.

## Configuration
Copy `settings.sample.ini` as `settings.ini` to configure oiseau. You can use environment variables as well.

Name | Default | Description |
---- | ------- | ----------- |
ONLINE_API_KEY | | Your online.net API key
C14_ALLOWED_SSH_KEYS | | A comma separated list of allowed online.net ssh keys identifiers (eg: ssh1,ssh2)
SSH_KEY_LOCATION | ~/.ssh/id_rsa.pub | Your SSH private key location. Must be added on C14.
C14_SYNC_NAME | sync | The name of your C14 sync
REPLAY_FOLDER | | Path to your replays folder
AVATARS_FOLDER | | Path to your avatars folder
AVATARS_FOLDER | | Path to your screenshots folder
PROFILE_BACKGROUNDS_FOLDER | | Path to your profile backgrounds folder
SYNC_REPLAYS | True | If True, sync replays
SYNC_AVATARS | True | If True, sync avatars
SYNC_SCREENSHOTS | True | If True, sync screenshots
SYNC_PROFILE_BACKGROUNDS | True | If True, sync profile backgrounds
SYNC_DATABASE | True | If True, dump and sync the database
COMPRESS_DATABASE | False | If True, the sql file will be gzipped before uploading it
DB_USERNAME | | MySQL username
DB_PASSWORD | | MySQL password
DB_NAME | ripple | MySQL database name
TELEGRAM_TOKEN | | Your Bot's Telegram API token. Leave empty to disable Telegram integration.
TELEGRAM_CHAT_ID | | The chat id to which the bot will send messages to

### Limitations
Unlike icebirb, oiseau doesn't currently support full backups, which is coming soon.

### Requirements
- Python 3 (tested on 3.6)  
- `rsync`, to sync data to C14's temporary storage
- `scp`, to check the latest sync date  
- `mysqldump`, to dump the database  
- Some python modules (run `pip install -r requirements.txt`)  

### License
This project is licensed under the GNU AGPL 3 License.  
See the "LICENSE" file for more information.
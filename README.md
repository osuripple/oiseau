# oiseau
## Ripple's data syncing and backup system using online.net's C14

### What's this?
This is a replacement for [icebirb](https://zxq.co/ripple/icebirb), our old sync and backup system. Recently we've switched to online.net's [C14](https://www.online.net/en/c14) cold storage solution and icebirb doesn't work really well with it, that's why we've replaced it with oiseau.

## How it works
This script checks if there's an open temporary space for our sync storage among our C14 safes, using online.net's API. If there's one, then it starts uploading data to it using rsync, if not it asks online.net to unarchive the sync storage to the temporary space and waits until the operation is completed. After 7 days, the temporary space is automatically archived by online.net.

## v2 changes
Version 2 only takes care of backing up replays. New replays must be stored in a temp folder (`./temp` as of right now, not configurable) and, when it's big enough, oiseau packs all temp replays in a .tar.gz file updating an index file that contains the max replay id for each archive as well. It then uploads the .tar.gz file and the index to C14 through FTP and empties the temp folder. We decided to do this and get rid of rsync because rsync is extremely slow with huge amount of files. The temp folder can be either a symlink to `lets/.data/local_replays` (oiseau will take care of deleting the temp replays as well, assuming they're uploaded to S3 too) or a folder that periodically receives new files added to `lets/.data/local_replays` on the main server through rsync. The latter is the recommended option if you have a dedicated server taking care of backing up to C14 and you're low on space on the main server.

## Configuration
Copy `settings.sample.ini` as `settings.ini` to configure oiseau. You can use environment variables as well.

Name | Default | Description |
---- | ------- | ----------- |
ONLINE_API_KEY | | Your online.net API key
C14_SYNC_NAME | sync | The name of your C14 sync
TELEGRAM_TOKEN | | Your Bot's Telegram API token. Leave empty to disable Telegram integration.
TELEGRAM_CHAT_ID | | The chat id to which the bot will send messages to

### Limitations
Unlike icebirb, oiseau doesn't currently support full backups, which is coming soon.

### Requirements
- Python 3 (tested on 3.7, should work with 3.6 as well)  
- Some python modules (run `pip install -r requirements.txt`)  

### License
This project is licensed under the GNU AGPL 3 License.  
See the "LICENSE" file for more information.

# oiseau
## Ripple's data syncing and backup system using online.net's C14

### What's this?
This is a replacement for [icebirb](https://zxq.co/ripple/icebirb), our old sync and backup system. Recently we've switched to online.net's [C14](https://www.online.net/en/c14) cold storage solution and icebirb doesn't work really well with it, that's why we've replaced it with oiseau.

## How it works
This script checks if there's an open temporary space for our sync storage among our C14 safes, using online.net's API. If there's one, then it starts uploading data to it using rsync, if not it asks online.net to unarchive the sync storage to the temporary space and waits until the operation is completed. After 7 days, the temporary space is automatically archived by online.net.

### Limitations
Unlike icebirb, oiseau doesn't currently support full backups, which is coming soon.

### Requirements
- Python 3 (tested on 3.6)  
- `rsync`, to sync data to C14's temporary storage  
- `mysqldump`, to dump the database  
- Some python modules (run `pip install -r requirements.txt`)  

### License
This project is licensed under the GNU AGPL 3 License.  
See the "LICENSE" file for more information.
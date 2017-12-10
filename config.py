from decouple import config
from decouple import Csv


class Config:
    def __init__(self):
        self._config = {
            "ONLINE_API_KEY": config("ONLINE_API_KEY", default=""),

            "C14_SYNC_NAME": config("C14_SYNC_NAME", default="sync"),
            "C14_ALLOWED_SSH_KEYS": config("C14_ALLOWED_SSH_KEYS", default="", cast=Csv(str)),

            "SYNC_REPLAYS": config("SYNC_REPLAYS", default="true", cast=bool),
            "SYNC_AVATARS": config("SYNC_AVATARS", default="true", cast=bool),
            "SYNC_SCREENSHOTS": config("SYNC_SCREENSHOTS", default="true", cast=bool),
            "SYNC_PROFILE_BACKGROUNDS": config("SYNC_PROFILE_BACKGROUNDS", default="true", cast=bool),
            "SYNC_DATABASE": config("SYNC_DATABASE", default="true", cast=bool),

            "REPLAYS_FOLDER": config("REPLAYS_FOLDER", default=""),
            "AVATARS_FOLDER": config("AVATARS_FOLDER", default=""),
            "SCREENSHOTS_FOLDER": config("SCREENSHOTS_FOLDER", default=""),
            "PROFILE_BACKGROUNDS_FOLDER": config("PROFILE_BACKGROUNDS_FOLDER", default=""),

            "DB_USERNAME": config("DB_USERNAME", default=""),
            "DB_PASSWORD": config("DB_PASSWORD", default=""),
            "DB_NAME": config("DB_NAME", default=""),
        }

    def __getitem__(self, item):
        return self._config[item]

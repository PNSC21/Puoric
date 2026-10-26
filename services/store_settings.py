from flask import current_app

from database.db import db
from database.models import StoreSetting


def get_setting(key, config_fallback=""):
    setting = db.session.get(StoreSetting, key)
    if setting is not None:
        return setting.value
    return current_app.config.get(config_fallback, "") if config_fallback else ""


def save_setting(key, value):
    setting = db.session.get(StoreSetting, key)
    if setting is None:
        setting = StoreSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value

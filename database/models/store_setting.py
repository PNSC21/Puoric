from database.db import db


class StoreSetting(db.Model):
    __tablename__ = "store_settings"

    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text, nullable=False, default="")
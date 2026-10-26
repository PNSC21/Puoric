from database.db import db
from database.models.base import BaseModel


class AccountEmail(BaseModel):
    __tablename__ = "account_emails"

    email = db.Column(db.String(120), nullable=False, unique=True)
    account_type = db.Column(db.String(12), nullable=False)
    account_id = db.Column(db.Integer, nullable=False)

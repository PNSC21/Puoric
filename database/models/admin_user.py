from werkzeug.security import check_password_hash, generate_password_hash

from database.db import db
from database.models.base import BaseModel


class AdminUser(BaseModel):
    __tablename__ = "admin_users"

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
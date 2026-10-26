from database.db import db
from database.models.base import BaseModel


class Customer(BaseModel):

    __tablename__ = "customers"

    full_name = db.Column(
        db.String(120),
        nullable=False
    )

    phone = db.Column(
        db.String(15),
        nullable=False,
        unique=True
    )

    email = db.Column(
        db.String(120),
        unique=True
    )

    password_hash = db.Column(
        db.String(255)
    )

    age = db.Column(db.Integer)

    gender = db.Column(db.String(30))

    skin_type = db.Column(db.String(80))

    allergies = db.Column(db.Text)

    address = db.Column(
        db.Text,
        nullable=False
    )

    city = db.Column(
        db.String(80),
        nullable=False
    )

    state = db.Column(
        db.String(80),
        nullable=False
    )

    country = db.Column(
        db.String(80),
        default="India",
        nullable=False
    )

    pincode = db.Column(
        db.String(10),
        nullable=False
    )

    notes = db.Column(
        db.Text
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    orders = db.relationship(
        "Order",
        back_populates="customer",
        lazy=True
    )

    addresses = db.relationship(
        "CustomerAddress",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Customer {self.full_name}>"
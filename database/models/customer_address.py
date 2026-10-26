from database.db import db
from database.models.base import BaseModel


class CustomerAddress(BaseModel):
    __tablename__ = "customer_addresses"

    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id"), nullable=False
    )
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(80), nullable=False)
    state = db.Column(db.String(80), nullable=False)
    country = db.Column(db.String(80), default="India", nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    customer = db.relationship("Customer", back_populates="addresses")

    @property
    def formatted(self):
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.pincode,
            self.country,
        ]
        return ", ".join(part for part in parts if part)
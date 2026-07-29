from database.db import db
from database.models.base import BaseModel


class Payment(BaseModel):

    __tablename__ = "payments"

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True
    )

    amount = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    payment_method = db.Column(
        db.String(30),
        default="UPI",
        nullable=False
    )

    transaction_id = db.Column(
        db.String(100),
        unique=True
    )

    payment_status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    paid_at = db.Column(
        db.DateTime
    )

    remarks = db.Column(
        db.Text
    )

    order = db.relationship(
        "Order",
        back_populates="payment"
    )

    def __repr__(self):
        return f"<Payment {self.transaction_id}>"
from database.db import db
from database.models.base import BaseModel


class Order(BaseModel):

    __tablename__ = "orders"

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=False
    )

    order_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    total_amount = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    payment_method = db.Column(
        db.String(30),
        default="UPI",
        nullable=False
    )

    payment_status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    order_status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    shipping_status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    customer_note = db.Column(
        db.Text
    )

    admin_note = db.Column(
        db.Text
    )

    customer = db.relationship(
        "Customer",
        back_populates="orders"
    )

    order_items = db.relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy=True
    )

    payment = db.relationship(
        "Payment",
        back_populates="order",
        uselist=False
    )

    def __repr__(self):
        return f"<Order {self.order_number}>"
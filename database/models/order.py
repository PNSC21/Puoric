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

    subtotal_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    discount_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    shipping_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    promotion_id = db.Column(db.Integer, db.ForeignKey("promotions.id"))

    promotion_name = db.Column(db.String(120))

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

    shipping_name = db.Column(
        db.String(120),
        nullable=False,
        default=""
    )

    shipping_phone = db.Column(
        db.String(20),
        nullable=False,
        default=""
    )

    shipping_state = db.Column(
        db.String(80),
        nullable=False,
        default=""
    )

    shipping_country = db.Column(
        db.String(80),
        nullable=False,
        default=""
    )

    shipping_address = db.Column(
        db.Text,
        nullable=False,
        default=""
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

    promotion = db.relationship("Promotion", back_populates="orders")

    def __repr__(self):
        return f"<Order {self.order_number}>"
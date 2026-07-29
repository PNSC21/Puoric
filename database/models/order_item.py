from database.db import db
from database.models.base import BaseModel


class OrderItem(BaseModel):

    __tablename__ = "order_items"

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False
    )

    quantity = db.Column(
        db.Integer,
        default=1,
        nullable=False
    )

    unit_price = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    subtotal = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    order = db.relationship(
        "Order",
        back_populates="order_items"
    )

    product = db.relationship(
        "Product",
        back_populates="order_items"
    )

    def __repr__(self):
        return f"<OrderItem {self.id}>"
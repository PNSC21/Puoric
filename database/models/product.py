from database.db import db
from database.models.base import BaseModel
from sqlalchemy import Numeric

class Product(BaseModel):

    __tablename__ = "products"

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    slug = db.Column(
        db.String(170),
        nullable=False,
        unique=True
    )

    sku = db.Column(
        db.String(60),
        nullable=False,
        unique=True
    )

    brand = db.Column(
        db.String(100),
        default="Puoric",
        nullable=False
    )

    short_description = db.Column(
        db.String(300)
    )

    description = db.Column(
        db.Text
    )

    ingredients = db.Column(
        db.Text
    )

    benefits = db.Column(
        db.Text
    )

    how_to_use = db.Column(
        db.Text
    )

    suitable_for = db.Column(
        db.String(255)
    )

    price = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    discount_price = db.Column(
        db.Numeric(10, 2)
    )

    stock = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    low_stock_limit = db.Column(
        db.Integer,
        default=5,
        nullable=False
    )

    image = db.Column(
        db.String(255)
    )

    is_featured = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    category = db.relationship(
        "Category",
        back_populates="products"
    )

    order_items = db.relationship(
        "OrderItem",
        back_populates="product",
        lazy=True
    )

    def __repr__(self):
        return f"<Product {self.name}>"
from database.db import db
from database.models.base import BaseModel


promotion_categories = db.Table(
    "promotion_categories",
    db.Column("promotion_id", db.Integer, db.ForeignKey("promotions.id"), primary_key=True),
    db.Column("category_id", db.Integer, db.ForeignKey("categories.id"), primary_key=True),
)

promotion_products = db.Table(
    "promotion_products",
    db.Column("promotion_id", db.Integer, db.ForeignKey("promotions.id"), primary_key=True),
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
)


class Promotion(BaseModel):
    __tablename__ = "promotions"

    name = db.Column(db.String(120), nullable=False)
    discount_type = db.Column(db.String(12), nullable=False)
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    target_scope = db.Column(db.String(12), nullable=False, default="all")
    applies_to_all_categories = db.Column(db.Boolean, nullable=False, default=True)
    festival_name = db.Column(db.String(80))
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    minimum_age = db.Column(db.Integer)
    maximum_age = db.Column(db.Integer)
    gender = db.Column(db.String(30))
    new_clients_only = db.Column(db.Boolean, nullable=False, default=False)
    minimum_orders = db.Column(db.Integer)
    maximum_orders = db.Column(db.Integer)
    minimum_spend = db.Column(db.Numeric(10, 2))
    maximum_spend = db.Column(db.Numeric(10, 2))
    minimum_order_amount = db.Column(db.Numeric(10, 2))

    orders = db.relationship("Order", back_populates="promotion")

    categories = db.relationship(
        "Category",
        secondary=promotion_categories,
        back_populates="promotions",
    )
    products = db.relationship(
        "Product",
        secondary=promotion_products,
        back_populates="promotions",
    )

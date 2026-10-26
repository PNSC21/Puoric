from database.db import db
from database.models.base import BaseModel


class ProductVariant(BaseModel):
    __tablename__ = "product_variants"

    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False
    )
    name = db.Column(db.String(80), nullable=False)
    value = db.Column(db.String(120), nullable=False)
    unit = db.Column(db.String(20))
    sku = db.Column(db.String(60), nullable=False, unique=True)
    price = db.Column(db.Numeric(10, 2))
    stock = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    product = db.relationship("Product", back_populates="variants")

    @property
    def low_stock(self):
        return 0 < self.stock <= self.product.low_stock_limit
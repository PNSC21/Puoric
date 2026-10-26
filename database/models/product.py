from database.db import db
from decimal import Decimal, ROUND_HALF_UP
from database.models.base import BaseModel

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

    discount_type = db.Column(
        db.String(12),
        nullable=False,
        default="none",
    )

    discount_value = db.Column(
        db.Numeric(10, 2),
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

    characteristics = db.relationship(
        "ProductCharacteristic",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy=True
    )

    variants = db.relationship(
        "ProductVariant",
        back_populates="product",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Product {self.name}>"

    @property
    def available_stock(self):
        if self.variants:
            return sum(
                variant.stock for variant in self.variants if variant.is_active
            )
        return self.stock

    @property
    def low_stock(self):
        return 0 < self.available_stock <= self.low_stock_limit

    def sale_price(self, price=None):
        regular_price = Decimal(price if price is not None else self.price)
        if self.discount_type == "percent" and self.discount_value:
            amount = regular_price * Decimal(self.discount_value) / Decimal("100")
        elif self.discount_type == "amount" and self.discount_value:
            amount = Decimal(self.discount_value)
        else:
            return regular_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return (regular_price - amount).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
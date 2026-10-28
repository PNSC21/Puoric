from database.db import db
from database.models.base import BaseModel


class Category(BaseModel):

    __tablename__ = "categories"

    name = db.Column(
        db.String(100),
        nullable=False
    )

    slug = db.Column(
        db.String(120),
        nullable=False,
        unique=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    image = db.Column(
        db.String(255),
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    products = db.relationship(
        "Product",
        back_populates="category",
        lazy=True
    )

    characteristic_tags = db.relationship(
        "CategoryCharacteristic",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="CategoryCharacteristic.name",
    )

    variant_types = db.relationship(
        "CategoryVariantType",
        back_populates="category",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="CategoryVariantType.name",
    )

    promotions = db.relationship(
        "Promotion",
        secondary="promotion_categories",
        back_populates="categories",
    )

    def __repr__(self):
        return f"<Category {self.name}>"
from database.db import db
from database.models.base import BaseModel


class CategoryVariantType(BaseModel):
    __tablename__ = "category_variant_types"
    __table_args__ = (
        db.UniqueConstraint("category_id", "name", name="uq_category_variant_type"),
    )

    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False
    )
    name = db.Column(db.String(80), nullable=False)

    category = db.relationship("Category", back_populates="variant_types")
    units = db.relationship(
        "CategoryVariantUnit",
        back_populates="variant_type",
        cascade="all, delete-orphan",
        order_by="CategoryVariantUnit.name",
    )

from database.db import db
from database.models.base import BaseModel


class CategoryVariantUnit(BaseModel):
    __tablename__ = "category_variant_units"
    __table_args__ = (
        db.UniqueConstraint("variant_type_id", "name", name="uq_category_variant_unit"),
    )

    variant_type_id = db.Column(
        db.Integer, db.ForeignKey("category_variant_types.id"), nullable=False
    )
    name = db.Column(db.String(20), nullable=False)

    variant_type = db.relationship("CategoryVariantType", back_populates="units")

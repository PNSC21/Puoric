from database.db import db
from database.models.base import BaseModel


class CategoryCharacteristic(BaseModel):
    __tablename__ = "category_characteristics"
    __table_args__ = (
        db.UniqueConstraint("category_id", "name", name="uq_category_characteristic"),
    )

    category_id = db.Column(
        db.Integer, db.ForeignKey("categories.id"), nullable=False
    )
    name = db.Column(db.String(80), nullable=False)

    category = db.relationship("Category", back_populates="characteristic_tags")
    values = db.relationship(
        "CategoryCharacteristicValue",
        back_populates="characteristic",
        cascade="all, delete-orphan",
        order_by="CategoryCharacteristicValue.value",
    )

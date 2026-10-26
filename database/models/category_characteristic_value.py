from database.db import db
from database.models.base import BaseModel


class CategoryCharacteristicValue(BaseModel):
    __tablename__ = "category_characteristic_values"
    __table_args__ = (
        db.UniqueConstraint(
            "characteristic_id", "value", name="uq_characteristic_value"
        ),
    )

    characteristic_id = db.Column(
        db.Integer,
        db.ForeignKey("category_characteristics.id"),
        nullable=False,
    )
    value = db.Column(db.String(255), nullable=False)

    characteristic = db.relationship(
        "CategoryCharacteristic", back_populates="values"
    )

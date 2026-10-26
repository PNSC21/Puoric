from database.db import db
from database.models.base import BaseModel


class ProductCharacteristic(BaseModel):
    __tablename__ = "product_characteristics"

    product_id = db.Column(
        db.Integer, db.ForeignKey("products.id"), nullable=False
    )
    name = db.Column(db.String(80), nullable=False)
    value = db.Column(db.String(255), nullable=False)

    product = db.relationship("Product", back_populates="characteristics")
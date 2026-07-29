from database.db import db
from database.models.base import BaseModel


class BeautyAdvisor(BaseModel):

    __tablename__ = "beauty_advisors"

    customer_name = db.Column(
        db.String(120),
        nullable=False
    )

    phone = db.Column(
        db.String(15),
        nullable=False
    )

    email = db.Column(
        db.String(120)
    )

    age = db.Column(
        db.Integer
    )

    gender = db.Column(
        db.String(20)
    )

    concern_type = db.Column(
        db.String(30),
        nullable=False
    )

    concern = db.Column(
        db.String(200),
        nullable=False
    )

    additional_notes = db.Column(
        db.Text
    )

    recommendation = db.Column(
        db.Text
    )

    status = db.Column(
        db.String(20),
        default="Pending",
        nullable=False
    )

    recommended_product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id")
    )

    recommended_product = db.relationship(
        "Product"
    )

    def __repr__(self):
        return f"<BeautyAdvisor {self.customer_name}>"
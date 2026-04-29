"""Department entity."""
from extensions import db
from models.mixins import TimestampMixin


class Department(TimestampMixin, db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)

    users = db.relationship("User", back_populates="department", lazy="dynamic")

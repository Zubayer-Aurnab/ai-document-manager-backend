"""Singleton row (id=1) for organization branding and contact info."""

from extensions import db
from models.mixins import TimestampMixin


class CompanySettings(TimestampMixin, db.Model):
    __tablename__ = "company_settings"

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(200), nullable=True)
    legal_name = db.Column(db.String(200), nullable=True)
    tagline = db.Column(db.String(300), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address_line1 = db.Column(db.String(200), nullable=True)
    address_line2 = db.Column(db.String(200), nullable=True)
    city = db.Column(db.String(120), nullable=True)
    state_region = db.Column(db.String(120), nullable=True)
    postal_code = db.Column(db.String(40), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    website = db.Column(db.String(300), nullable=True)

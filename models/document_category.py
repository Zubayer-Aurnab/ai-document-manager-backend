"""Document category (controlled vocabulary for document.category_slug)."""

from extensions import db
from models.mixins import TimestampMixin


class DocumentCategory(TimestampMixin, db.Model):
    __tablename__ = "document_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(40), unique=True, nullable=False, index=True)

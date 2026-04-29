"""Document metadata and soft delete."""
import enum

from extensions import db
from models.mixins import TimestampMixin


class DocumentVisibility(str, enum.Enum):
    PRIVATE = "private"
    DEPARTMENT = "department"
    # Only owner + explicit shares (same effective rules as private; distinct for UI / filtering).
    SHARED = "shared"


class Document(TimestampMixin, db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True, index=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=True)
    tags = db.Column(db.JSON, nullable=True)
    original_filename = db.Column(db.String(500), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(120), nullable=False)
    size_bytes = db.Column(db.BigInteger, nullable=False)
    extension = db.Column(db.String(20), nullable=False)
    visibility = db.Column(
        db.String(20), nullable=False, default=DocumentVisibility.DEPARTMENT.value
    )
    category_slug = db.Column(db.String(40), nullable=True, index=True)
    extracted_text = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    ai_keywords = db.Column(db.JSON, nullable=True)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    owner = db.relationship("User", foreign_keys=[owner_id], backref=db.backref("owned_documents", lazy="dynamic"))
    shares = db.relationship("DocumentShare", back_populates="document", cascade="all, delete-orphan")

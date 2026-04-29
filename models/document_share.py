"""Share grants to users or departments."""
import enum

from extensions import db
from models.mixins import TimestampMixin


class SharePermission(str, enum.Enum):
    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"


class DocumentShare(TimestampMixin, db.Model):
    __tablename__ = "document_shares"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False, index=True)
    shared_with_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    shared_with_department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=True, index=True
    )
    permission = db.Column(db.String(20), nullable=False, default=SharePermission.VIEW.value)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    document = db.relationship("Document", back_populates="shares")
    shared_with_user = db.relationship("User", foreign_keys=[shared_with_user_id])
    shared_with_department = db.relationship("Department", foreign_keys=[shared_with_department_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])

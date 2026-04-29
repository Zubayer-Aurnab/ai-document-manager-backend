"""Audit trail for document and admin actions."""
from extensions import db
from models.mixins import TimestampMixin


class ActivityLog(TimestampMixin, db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    metadata_json = db.Column(db.JSON, nullable=True)

    user = db.relationship("User", backref=db.backref("activity_logs", lazy="dynamic"))

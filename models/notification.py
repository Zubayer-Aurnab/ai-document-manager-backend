"""In-app notifications."""
from extensions import db
from models.mixins import TimestampMixin


class Notification(TimestampMixin, db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)

    user = db.relationship("User", backref=db.backref("notifications", lazy="dynamic"))
    document = db.relationship("Document")

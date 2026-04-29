"""Activity log persistence."""
from extensions import db
from models.activity_log import ActivityLog


class ActivityLogRepository:
    def create(self, log: ActivityLog) -> ActivityLog:
        db.session.add(log)
        db.session.commit()
        return log

    def list_recent(self, page: int, per_page: int, document_id: int | None = None):
        q = ActivityLog.query.order_by(ActivityLog.created_at.desc())
        if document_id is not None:
            q = q.filter(
                ActivityLog.entity_type == "document",
                ActivityLog.entity_id == document_id,
            )
        return q.paginate(page=page, per_page=per_page, error_out=False)

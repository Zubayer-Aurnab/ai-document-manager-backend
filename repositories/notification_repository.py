"""Notification persistence."""
from datetime import datetime, timezone
from typing import Optional

from extensions import db
from models.notification import Notification


class NotificationRepository:
    def get_by_id(self, notif_id: int) -> Optional[Notification]:
        return db.session.get(Notification, notif_id)

    def list_for_user(self, user_id: int, page: int, per_page: int, unread_only: bool = False):
        q = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc())
        if unread_only:
            q = q.filter(Notification.read_at.is_(None))
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def create(self, n: Notification) -> Notification:
        db.session.add(n)
        db.session.commit()
        return n

    def save(self, n: Notification) -> Notification:
        db.session.add(n)
        db.session.commit()
        return n

    def mark_all_read_for_user(self, user_id: int) -> int:
        now = datetime.now(timezone.utc)
        count = (
            Notification.query.filter_by(user_id=user_id)
            .filter(Notification.read_at.is_(None))
            .update({"read_at": now}, synchronize_session=False)
        )
        db.session.commit()
        return int(count)

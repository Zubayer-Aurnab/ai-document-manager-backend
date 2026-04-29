"""Create and manage notifications."""
from datetime import datetime, timezone

from models.notification import Notification
from repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository | None = None):
        self._repo = repo or NotificationRepository()

    def notify(
        self,
        user_id: int,
        type_: str,
        title: str,
        body: str | None = None,
        document_id: int | None = None,
    ) -> Notification:
        n = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
            document_id=document_id,
        )
        return self._repo.create(n)

    def list_for_user(self, user_id: int, page: int, per_page: int, unread_only: bool = False):
        return self._repo.list_for_user(user_id, page, per_page, unread_only)

    def mark_read(self, notif_id: int, user_id: int) -> Notification | None:
        n = self._repo.get_by_id(notif_id)
        if not n or n.user_id != user_id:
            return None
        n.read_at = datetime.now(timezone.utc)
        return self._repo.save(n)

    def mark_all_read(self, user_id: int) -> int:
        return self._repo.mark_all_read_for_user(user_id)

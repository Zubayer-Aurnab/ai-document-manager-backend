"""Write and query activity logs."""
from typing import Any, Optional

from models.activity_log import ActivityLog
from repositories.activity_log_repository import ActivityLogRepository


class ActivityLogService:
    def __init__(self, repo: Optional[ActivityLogRepository] = None):
        self._repo = repo or ActivityLogRepository()

    def record(
        self,
        user_id: Optional[int],
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ActivityLog:
        log = ActivityLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
        return self._repo.create(log)

    def list_paginated(self, page: int, per_page: int, document_id: int | None = None):
        return self._repo.list_recent(page=page, per_page=per_page, document_id=document_id)

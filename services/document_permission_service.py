"""Resolve document permissions for a user (backend source of truth)."""
from datetime import datetime, timezone
from typing import Optional

from models.document import Document, DocumentVisibility
from models.document_share import DocumentShare, SharePermission
from models.user import User, UserRole


_ORDER = {SharePermission.VIEW.value: 1, SharePermission.COMMENT.value: 2, SharePermission.EDIT.value: 3}


def _share_is_active(sh: DocumentShare) -> bool:
    exp = getattr(sh, "expires_at", None)
    if exp is None:
        return True
    now = datetime.now(timezone.utc)
    return now <= exp


def _max_perm(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if a is None:
        return b
    if b is None:
        return a
    return a if _ORDER[a] >= _ORDER[b] else b


class DocumentPermissionService:
    """Enforces view / comment / edit semantics on the server."""

    def effective_permission(self, user: User, document: Document | None) -> Optional[str]:
        if not document or document.deleted_at is not None:
            return None
        if user.role == UserRole.ADMIN.value:
            return SharePermission.EDIT.value
        if document.owner_id == user.id:
            return SharePermission.EDIT.value

        best: Optional[str] = None
        for sh in document.shares:
            if not _share_is_active(sh):
                continue
            granted: Optional[str] = None
            if sh.shared_with_user_id == user.id:
                granted = sh.permission
            elif (
                user.department_id is not None
                and sh.shared_with_department_id == user.department_id
            ):
                granted = sh.permission
            if granted:
                best = _max_perm(best, granted)

        if (
            document.visibility == DocumentVisibility.DEPARTMENT.value
            and user.department_id is not None
            and document.department_id == user.department_id
        ):
            best = _max_perm(best, SharePermission.VIEW.value)

        return best

    def require_at_least(self, user: User, document: Document, minimum: str) -> bool:
        eff = self.effective_permission(user, document)
        if eff is None:
            return False
        return _ORDER[eff] >= _ORDER[minimum]

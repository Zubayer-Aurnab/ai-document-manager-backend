"""Document lifecycle, sharing, and secure file access."""
from datetime import datetime, timezone
from typing import Any, Optional

from flask import current_app
from werkzeug.datastructures import FileStorage

from models.document import Document, DocumentVisibility
from models.document_share import DocumentShare, SharePermission
from models.user import User, UserRole
from repositories.document_repository import DocumentRepository
from repositories.document_share_repository import DocumentShareRepository
from repositories.user_repository import UserRepository
from services.activity_log_service import ActivityLogService
from services.document_permission_service import DocumentPermissionService
from services.notification_service import NotificationService
from services.storage_service import StorageService
from services.text_extraction_service import TextExtractionService
from utils.file_security import safe_stored_name
from repositories.document_category_repository import DocumentCategoryRepository


def _valid_category_slugs() -> set[str]:
    return {c.slug for c in DocumentCategoryRepository().list_all_ordered()}

_ALLOWED_VISIBILITY = frozenset(
    {
        DocumentVisibility.PRIVATE.value,
        DocumentVisibility.DEPARTMENT.value,
        DocumentVisibility.SHARED.value,
    }
)


def _normalize_tags(raw: list[str] | None) -> list[str] | None:
    if not raw:
        return None
    out = [str(x).strip()[:40] for x in raw if str(x).strip()]
    return out[:25] or None


_VALID_SHARE_PERMS = {
    SharePermission.VIEW.value,
    SharePermission.COMMENT.value,
    SharePermission.EDIT.value,
}


class DocumentService:
    def __init__(
        self,
        docs: DocumentRepository | None = None,
        shares: DocumentShareRepository | None = None,
        users: UserRepository | None = None,
        storage: StorageService | None = None,
        text_extraction: TextExtractionService | None = None,
        perm: DocumentPermissionService | None = None,
        logs: ActivityLogService | None = None,
        notifications: NotificationService | None = None,
    ):
        self._docs = docs or DocumentRepository()
        self._shares = shares or DocumentShareRepository()
        self._users = users or UserRepository()
        self._storage = storage or StorageService()
        self._text = text_extraction or TextExtractionService()
        self._perm = perm or DocumentPermissionService()
        self._logs = logs or ActivityLogService()
        self._notifications = notifications or NotificationService()

    def upload(
        self,
        actor: User,
        file: FileStorage,
        title: str,
        visibility: str,
        category_slug: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
    ) -> tuple[Optional[Document], Optional[str]]:
        if not file or not file.filename:
            return None, "No file"
        allowed = current_app.config["ALLOWED_EXTENSIONS"]
        try:
            stored_name, ext = safe_stored_name(file.filename, allowed)
        except ValueError as e:
            return None, str(e)

        mime = file.mimetype or "application/octet-stream"
        allowed_mimes = current_app.config["ALLOWED_MIME_TYPES"]
        if mime not in allowed_mimes and not mime.startswith("image/"):
            return None, "Unsupported MIME type"

        raw = file.read()
        if not raw:
            return None, "Empty file"

        self._storage.save_bytes(stored_name, raw)

        vis = visibility if visibility in _ALLOWED_VISIBILITY else DocumentVisibility.DEPARTMENT.value

        cat = (category_slug or "").strip() or None
        if cat is not None and cat not in _valid_category_slugs():
            return None, "Invalid category_slug"

        desc = (description or "").strip() or None
        if desc and len(desc) > 8000:
            desc = desc[:8000]
        tag_list = _normalize_tags(tags)

        document = Document(
            owner_id=actor.id,
            department_id=actor.department_id,
            title=title.strip() or file.filename,
            description=desc,
            tags=tag_list,
            original_filename=file.filename,
            stored_filename=stored_name,
            mime_type=mime,
            size_bytes=len(raw),
            extension=ext,
            visibility=vis,
            category_slug=cat,
        )
        path = self._storage.absolute_path(stored_name)
        document.extracted_text = self._text.extract(path, ext, mime)[:1_000_000]
        self._docs.create(document)
        self._logs.record(actor.id, "document.uploaded", "document", document.id, {"title": document.title})
        return document, None

    def get_document(self, doc_id: int) -> Optional[Document]:
        return self._docs.get_by_id_with_shares(doc_id)

    def list_my(self, actor: User, page: int, per_page: int, filters: dict[str, Any] | None = None):
        return self._docs.list_my(actor.id, page, per_page, filters)

    def list_department(
        self,
        actor: User,
        department_id: Optional[int],
        page: int,
        per_page: int,
        filters: dict[str, Any] | None = None,
    ) -> tuple[Any, Optional[str]]:
        if department_id is None:
            if actor.role != UserRole.ADMIN.value:
                return None, "department_id is required."
            return self._docs.list_all_departments_admin(page, per_page, filters), None
        if actor.role != UserRole.ADMIN.value:
            if actor.department_id != department_id:
                return None, "Forbidden"
        return self._docs.list_department(department_id, page, per_page, actor, filters), None

    def list_shared(self, actor: User, page: int, per_page: int, filters: dict[str, Any] | None = None):
        return self._docs.list_shared_with_user(actor.id, actor.department_id, page, per_page, actor, filters)

    def list_all_admin(
        self, actor: User, page: int, per_page: int, filters: dict[str, Any] | None = None
    ) -> tuple[Any, Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        return self._docs.list_all_admin(page, per_page, filters), None

    def update_metadata(self, actor: User, doc_id: int, data: dict[str, Any]) -> tuple[Optional[Document], Optional[str]]:
        doc = self.get_document(doc_id)
        if not doc:
            return None, "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.EDIT.value):
            return None, "Forbidden"
        if "title" in data and data["title"] is not None:
            doc.title = str(data["title"]).strip()
        if "visibility" in data and data["visibility"] is not None:
            v = data["visibility"]
            if v in _ALLOWED_VISIBILITY:
                doc.visibility = v
        if "description" in data:
            d = data["description"]
            if d is None:
                doc.description = None
            else:
                s = str(d).strip()
                doc.description = (s[:8000] if s else None)
        if "tags" in data:
            t = data["tags"]
            if t is None:
                doc.tags = None
            elif isinstance(t, list):
                doc.tags = _normalize_tags([str(x) for x in t])
            else:
                return None, "Invalid tags"
        if "category_slug" in data:
            cs = data["category_slug"]
            if cs is None or cs == "":
                doc.category_slug = None
            elif cs in _valid_category_slugs():
                doc.category_slug = cs
            else:
                return None, "Invalid category"
        self._docs.save(doc)
        self._logs.record(actor.id, "document.updated", "document", doc.id, {})
        return doc, None

    def soft_delete(self, actor: User, doc_id: int) -> Optional[str]:
        doc = self.get_document(doc_id)
        if not doc:
            return "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.EDIT.value):
            return "Forbidden"
        doc.deleted_at = datetime.now(timezone.utc)
        self._docs.save(doc)
        self._logs.record(actor.id, "document.deleted", "document", doc.id, {})
        return None

    def share(
        self,
        actor: User,
        doc_id: int,
        shared_with_user_id: int | None,
        shared_with_department_id: int | None,
        permission: str,
        expires_at: datetime | None = None,
    ) -> tuple[Optional[DocumentShare], Optional[str]]:
        doc = self.get_document(doc_id)
        if not doc:
            return None, "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.EDIT.value):
            return None, "Forbidden"
        if bool(shared_with_user_id) == bool(shared_with_department_id):
            return None, "Specify exactly one of user or department"
        if permission not in _VALID_SHARE_PERMS:
            return None, "Invalid permission"
        sh = DocumentShare(
            document_id=doc.id,
            shared_with_user_id=shared_with_user_id,
            shared_with_department_id=shared_with_department_id,
            permission=permission,
            expires_at=expires_at,
            created_by_id=actor.id,
        )
        self._shares.create(sh)
        self._logs.record(actor.id, "document.shared", "document", doc.id, {"share_id": sh.id})
        target_user_id = shared_with_user_id
        if target_user_id:
            self._notifications.notify(
                target_user_id,
                "document_shared",
                "Document shared with you",
                f"{actor.full_name} shared “{doc.title}”",
                document_id=doc.id,
            )
        if shared_with_department_id:
            for u in User.query.filter_by(
                department_id=shared_with_department_id,
                is_active=True,
            ).all():
                if u.id == actor.id:
                    continue
                self._notifications.notify(
                    u.id,
                    "document_shared",
                    "Document shared with your department",
                    f"{actor.full_name} shared “{doc.title}” with your department",
                    document_id=doc.id,
                )
        return sh, None

    def revoke_share(self, actor: User, doc_id: int, share_id: int) -> Optional[str]:
        doc = self.get_document(doc_id)
        if not doc:
            return "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.EDIT.value):
            return "Forbidden"
        sh = self._shares.get_by_id(share_id)
        if not sh or sh.document_id != doc.id:
            return "Not found"
        self._shares.delete(sh)
        self._logs.record(actor.id, "document.share_revoked", "document", doc.id, {"share_id": share_id})
        return None

    def list_shares(self, actor: User, doc_id: int) -> tuple[list[DocumentShare], Optional[str]]:
        doc = self.get_document(doc_id)
        if not doc:
            return [], "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.VIEW.value):
            return [], "Forbidden"
        return self._shares.list_for_document(doc_id), None

    def file_delivery(
        self, actor: User, doc_id: int, for_download: bool
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        doc = self.get_document(doc_id)
        if not doc:
            return None, "Not found"
        if not self._perm.require_at_least(actor, doc, SharePermission.VIEW.value):
            return None, "Forbidden"
        path = self._storage.absolute_path(doc.stored_filename)
        if not path.is_file():
            return None, "File missing"
        return {
            "path": path,
            "mimetype": doc.mime_type,
            "download_name": doc.original_filename if for_download else None,
            "as_attachment": for_download,
        }, None

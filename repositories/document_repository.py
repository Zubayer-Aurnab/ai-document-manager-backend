"""Document queries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from extensions import db
from models.document import Document, DocumentVisibility
from models.user import User, UserRole


def _parse_date_start(s: str | None) -> datetime | None:
    if not s or not str(s).strip():
        return None
    try:
        return datetime.fromisoformat(str(s)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_date_end_exclusive(s: str | None) -> datetime | None:
    start = _parse_date_start(s)
    if start is None:
        return None
    return start + timedelta(days=1)


class DocumentRepository:
    def get_by_id(self, doc_id: int, include_deleted: bool = False) -> Optional[Document]:
        q = Document.query.filter_by(id=doc_id)
        if not include_deleted:
            q = q.filter(Document.deleted_at.is_(None))
        return q.first()

    def get_by_id_with_shares(self, doc_id: int, include_deleted: bool = False) -> Optional[Document]:
        q = Document.query.options(joinedload(Document.shares)).filter_by(id=doc_id)
        if not include_deleted:
            q = q.filter(Document.deleted_at.is_(None))
        return q.first()

    def get_by_stored_filename(self, stored: str) -> Optional[Document]:
        return (
            Document.query.filter_by(stored_filename=stored)
            .filter(Document.deleted_at.is_(None))
            .first()
        )

    def create(self, document: Document) -> Document:
        db.session.add(document)
        db.session.commit()
        return document

    def save(self, document: Document) -> Document:
        db.session.add(document)
        db.session.commit()
        return document

    def _apply_list_filters(
        self,
        q,
        *,
        search: str | None = None,
        extension: str | None = None,
        category_slug: str | None = None,
        visibility: str | None = None,
        owner_id: int | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
    ):
        if search and str(search).strip():
            like = f"%{str(search).strip()}%"
            q = q.filter(
                or_(
                    Document.title.ilike(like),
                    Document.original_filename.ilike(like),
                )
            )
        if extension and str(extension).strip():
            ext = str(extension).lower().lstrip(".")
            q = q.filter(Document.extension == ext)
        if category_slug and str(category_slug).strip():
            q = q.filter(Document.category_slug == str(category_slug).strip())
        if visibility in (
            DocumentVisibility.PRIVATE.value,
            DocumentVisibility.DEPARTMENT.value,
            DocumentVisibility.SHARED.value,
        ):
            q = q.filter(Document.visibility == visibility)
        if owner_id is not None:
            q = q.filter(Document.owner_id == owner_id)
        start = _parse_date_start(created_from)
        if start is not None:
            q = q.filter(Document.created_at >= start)
        end_excl = _parse_date_end_exclusive(created_to)
        if end_excl is not None:
            q = q.filter(Document.created_at < end_excl)
        return q

    def list_my(
        self,
        owner_id: int,
        page: int,
        per_page: int,
        filters: dict[str, Any] | None = None,
    ):
        filters = {k: v for k, v in (filters or {}).items() if k != "owner_id"}
        q = (
            Document.query.options(joinedload(Document.owner))
            .filter_by(owner_id=owner_id)
            .filter(Document.deleted_at.is_(None))
        )
        q = self._apply_list_filters(q, **filters)
        return q.order_by(Document.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    def list_department(
        self,
        department_id: int,
        page: int,
        per_page: int,
        viewer: User,
        filters: dict[str, Any] | None = None,
    ):
        filters = dict(filters or {})
        if viewer.role != UserRole.ADMIN.value:
            filters.pop("owner_id", None)
        q = Document.query.options(joinedload(Document.owner)).filter(
            Document.deleted_at.is_(None),
            Document.department_id == department_id,
        )
        if viewer.role != UserRole.ADMIN.value:
            q = q.filter(
                or_(
                    Document.visibility == DocumentVisibility.DEPARTMENT.value,
                    Document.owner_id == viewer.id,
                )
            )
        q = self._apply_list_filters(q, **filters)
        q = q.order_by(Document.created_at.desc())
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def list_all_departments_admin(
        self,
        page: int,
        per_page: int,
        filters: dict[str, Any] | None = None,
    ):
        """Admin aggregate: documents assigned to any department (all department libraries)."""
        q = Document.query.options(joinedload(Document.owner)).filter(
            Document.deleted_at.is_(None),
            Document.department_id.isnot(None),
        )
        q = self._apply_list_filters(q, **(filters or {}))
        q = q.order_by(Document.created_at.desc())
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def list_shared_with_user(
        self,
        user_id: int,
        department_id: Optional[int],
        page: int,
        per_page: int,
        viewer: User,
        filters: dict[str, Any] | None = None,
    ):
        from models.document_share import DocumentShare

        filters = dict(filters or {})
        if viewer.role != UserRole.ADMIN.value:
            filters.pop("owner_id", None)

        conds = [DocumentShare.shared_with_user_id == user_id]
        if department_id is not None:
            conds.append(DocumentShare.shared_with_department_id == department_id)
        q = (
            Document.query.options(joinedload(Document.owner))
            .join(DocumentShare, DocumentShare.document_id == Document.id)
            .filter(Document.deleted_at.is_(None), or_(*conds))
        )
        q = self._apply_list_filters(q, **filters)
        q = q.distinct().order_by(Document.created_at.desc())
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def list_all_admin(self, page: int, per_page: int, filters: dict[str, Any] | None = None):
        q = Document.query.options(joinedload(Document.owner)).filter(Document.deleted_at.is_(None))
        q = self._apply_list_filters(q, **(filters or {}))
        return q.order_by(Document.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    def search_authorized_ids(self, user: User, query_text: str, *, limit: int | None = None) -> list[int]:
        """Return document IDs the user may see that match search (SQL side), newest first.

        When ``limit`` is set, at most that many rows are returned (for AI re-ranking cap).
        """
        from models.document_share import DocumentShare
        from sqlalchemy import and_, exists, select

        like = f"%{query_text}%"
        text_match = or_(
            Document.title.ilike(like),
            Document.original_filename.ilike(like),
            Document.extracted_text.ilike(like),
        )
        base_deleted = Document.deleted_at.is_(None)

        if user.role == UserRole.ADMIN.value:
            q = (
                Document.query.filter(base_deleted, text_match)
                .order_by(Document.created_at.desc())
            )
            if limit is not None:
                q = q.limit(int(limit))
            return [r.id for r in q.all()]

        dept_id = user.department_id
        share_parts = [DocumentShare.shared_with_user_id == user.id]
        if dept_id is not None:
            share_parts.append(DocumentShare.shared_with_department_id == dept_id)
        share_subq = exists(
            select(DocumentShare.id).where(
                DocumentShare.document_id == Document.id,
                or_(*share_parts),
            )
        )
        access = or_(Document.owner_id == user.id, share_subq)
        if dept_id is not None:
            access = or_(
                access,
                and_(
                    Document.visibility == DocumentVisibility.DEPARTMENT.value,
                    Document.department_id == dept_id,
                ),
            )
        q = Document.query.filter(base_deleted, text_match, access).order_by(Document.created_at.desc())
        if limit is not None:
            q = q.limit(int(limit))
        return [r.id for r in q.all()]

    def list_authorized_recent_ids(self, user: User, limit: int) -> list[int]:
        """Non-deleted documents the user may access, newest first (no text filter). Used for NL AI search pool."""
        from models.document_share import DocumentShare
        from sqlalchemy import and_, exists, select

        base_deleted = Document.deleted_at.is_(None)
        lim = max(1, min(int(limit), 200))

        if user.role == UserRole.ADMIN.value:
            q = Document.query.filter(base_deleted).order_by(Document.created_at.desc()).limit(lim)
            return [r.id for r in q.all()]

        dept_id = user.department_id
        share_parts = [DocumentShare.shared_with_user_id == user.id]
        if dept_id is not None:
            share_parts.append(DocumentShare.shared_with_department_id == dept_id)
        share_subq = exists(
            select(DocumentShare.id).where(
                DocumentShare.document_id == Document.id,
                or_(*share_parts),
            )
        )
        access = or_(Document.owner_id == user.id, share_subq)
        if dept_id is not None:
            access = or_(
                access,
                and_(
                    Document.visibility == DocumentVisibility.DEPARTMENT.value,
                    Document.department_id == dept_id,
                ),
            )
        q = Document.query.filter(base_deleted, access).order_by(Document.created_at.desc()).limit(lim)
        return [r.id for r in q.all()]

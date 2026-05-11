"""Build LLM context blocks from authorized documents."""

from __future__ import annotations

from typing import Any

from flask import current_app
from sqlalchemy.orm import joinedload

from extensions import db
from models.department import Department
from models.document import Document
from models.user import User
from services.ai_workspace import limits
from services.document_permission_service import DocumentPermissionService


def _tags_list(d: Document) -> list[str]:
    raw = getattr(d, "tags", None)
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()][:25]
    return [str(raw).strip()] if str(raw).strip() else []


def _file_type_label(d: Document) -> str:
    ext = (d.extension or "").lstrip(".").upper()
    mime = d.mime_type or ""
    if ext and mime:
        return f"{ext} · {mime}"
    return mime or ext or "—"


class WorkspaceContextBuilder:
    """Packs extracted text from document IDs into one prompt-sized context string."""

    def __init__(self, perm: DocumentPermissionService | None = None):
        self._perm = perm or DocumentPermissionService()

    def build(
        self,
        user: User,
        ordered_doc_ids: list[int],
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Returns (context_for_llm, source_records matching AISearchHit-like shape for API).
        Stops adding documents when max_context_chars would be exceeded.
        """
        cfg = current_app.config
        cap_docs = limits.max_documents(cfg)
        per_doc = limits.chars_per_document(cfg)
        max_total = limits.max_context_chars(cfg)

        ids = ordered_doc_ids[:cap_docs]
        if not ids:
            return "", []

        rows = (
            Document.query.options(joinedload(Document.owner))
            .filter(Document.id.in_(ids))
            .filter(Document.deleted_at.is_(None))
            .all()
        )
        by_id = {r.id: r for r in rows}

        parts: list[str] = []
        sources: list[dict[str, Any]] = []
        used = 0

        for doc_id in ids:
            d = by_id.get(doc_id)
            if not d:
                continue
            perm = self._perm.effective_permission(user, d)
            if not perm:
                continue

            body = (d.extracted_text or "").strip()
            chunk = body[:per_doc] if body else ""
            if len(body) > per_doc:
                chunk += "\n… [truncated]"

            block = (
                f"--- DOCUMENT_ID: {d.id}\n"
                f"TITLE: {d.title or '—'}\n"
                f"FILENAME: {d.original_filename or '—'}\n"
                f"TAGS: {', '.join(_tags_list(d)) or '—'}\n"
                f"SUMMARY: {(d.ai_summary or '').strip()[:800] or '—'}\n"
                f"TEXT:\n{chunk or '(no extracted text)'}\n"
            )
            if used + len(block) > max_total:
                break
            parts.append(block)
            used += len(block)

            dept_name: str | None = None
            if d.department_id is not None:
                dept = db.session.get(Department, d.department_id)
                dept_name = dept.name if dept else None
            owner = d.owner
            sources.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "snippet": (chunk[:220] + "…") if len(chunk) > 220 else chunk,
                    "summary": (d.ai_summary or "").strip() or None,
                    "tags": _tags_list(d),
                    "matched_reason": "Used as context for this answer",
                    "file_type": _file_type_label(d),
                    "department": dept_name,
                    "owner": (
                        {"full_name": owner.full_name, "email": owner.email}
                        if owner
                        else None
                    ),
                    "permission": perm,
                }
            )

        return "\n".join(parts), sources

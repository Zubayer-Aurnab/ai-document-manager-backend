"""Document share persistence."""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from extensions import db
from models.document_share import DocumentShare


class DocumentShareRepository:
    def get_by_id(self, share_id: int) -> Optional[DocumentShare]:
        return db.session.get(DocumentShare, share_id)

    def list_for_document(self, document_id: int):
        return (
            DocumentShare.query.options(
                joinedload(DocumentShare.shared_with_user),
                joinedload(DocumentShare.shared_with_department),
            )
            .filter_by(document_id=document_id)
            .order_by(DocumentShare.created_at.desc())
            .all()
        )

    def active_share_summary_by_document_ids(self, document_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Per document: count of user shares + unique department names (non-expired shares)."""
        if not document_ids:
            return {}
        unique_ids = list(dict.fromkeys(document_ids))
        now = datetime.now(timezone.utc)
        shares = (
            DocumentShare.query.options(
                joinedload(DocumentShare.shared_with_user),
                joinedload(DocumentShare.shared_with_department),
            )
            .filter(
                DocumentShare.document_id.in_(unique_ids),
                or_(
                    DocumentShare.expires_at.is_(None),
                    DocumentShare.expires_at > now,
                ),
            )
            .order_by(DocumentShare.document_id.asc(), DocumentShare.id.asc())
            .all()
        )
        user_count: dict[int, int] = {}
        department_names: dict[int, list[str]] = {}
        seen_department: dict[int, set[str]] = {}
        for sh in shares:
            did = sh.document_id
            if sh.shared_with_user_id and sh.shared_with_user is not None:
                user_count[did] = user_count.get(did, 0) + 1
            elif sh.shared_with_department_id and sh.shared_with_department is not None:
                name = (sh.shared_with_department.name or "").strip()
                if not name:
                    continue
                if did not in seen_department:
                    seen_department[did] = set()
                    department_names[did] = []
                if name not in seen_department[did]:
                    seen_department[did].add(name)
                    department_names[did].append(name)
        return {
            did: {
                "user_count": user_count.get(did, 0),
                "departments": department_names.get(did, []),
            }
            for did in unique_ids
        }

    def create(self, share: DocumentShare) -> DocumentShare:
        db.session.add(share)
        db.session.commit()
        db.session.refresh(share)
        loaded = (
            DocumentShare.query.options(
                joinedload(DocumentShare.shared_with_user),
                joinedload(DocumentShare.shared_with_department),
            )
            .filter_by(id=share.id)
            .one_or_none()
        )
        return loaded or share

    def delete(self, share: DocumentShare) -> None:
        db.session.delete(share)
        db.session.commit()

    def save(self, share: DocumentShare) -> DocumentShare:
        db.session.add(share)
        db.session.commit()
        db.session.refresh(share)
        loaded = (
            DocumentShare.query.options(
                joinedload(DocumentShare.shared_with_user),
                joinedload(DocumentShare.shared_with_department),
            )
            .filter_by(id=share.id)
            .one_or_none()
        )
        return loaded or share

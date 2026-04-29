"""Document share persistence."""
from typing import Optional

from extensions import db
from models.document_share import DocumentShare


class DocumentShareRepository:
    def get_by_id(self, share_id: int) -> Optional[DocumentShare]:
        return db.session.get(DocumentShare, share_id)

    def list_for_document(self, document_id: int):
        return (
            DocumentShare.query.filter_by(document_id=document_id)
            .order_by(DocumentShare.created_at.desc())
            .all()
        )

    def create(self, share: DocumentShare) -> DocumentShare:
        db.session.add(share)
        db.session.commit()
        return share

    def delete(self, share: DocumentShare) -> None:
        db.session.delete(share)
        db.session.commit()

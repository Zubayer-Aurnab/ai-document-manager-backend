"""Document category persistence."""
from typing import Optional

from extensions import db
from models.document import Document
from models.document_category import DocumentCategory


class DocumentCategoryRepository:
    def get_by_id(self, category_id: int) -> Optional[DocumentCategory]:
        return db.session.get(DocumentCategory, category_id)

    def get_by_slug(self, slug: str) -> Optional[DocumentCategory]:
        return DocumentCategory.query.filter(DocumentCategory.slug == slug).first()

    def list_all_ordered(self) -> list[DocumentCategory]:
        return DocumentCategory.query.order_by(DocumentCategory.name.asc()).all()

    def create(self, row: DocumentCategory) -> DocumentCategory:
        db.session.add(row)
        db.session.commit()
        return row

    def save(self, row: DocumentCategory) -> DocumentCategory:
        db.session.add(row)
        db.session.commit()
        return row

    def delete(self, row: DocumentCategory) -> None:
        db.session.delete(row)
        db.session.commit()

    def count_documents_with_slug(self, slug: str) -> int:
        return Document.query.filter(Document.category_slug == slug, Document.deleted_at.is_(None)).count()

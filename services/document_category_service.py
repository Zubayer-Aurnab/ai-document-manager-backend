"""Document categories (DB-backed)."""
from typing import Optional

from models.document_category import DocumentCategory
from models.user import User, UserRole
from repositories.document_category_repository import DocumentCategoryRepository
from utils.slugify import slugify


class DocumentCategoryService:
    def __init__(self, repo: DocumentCategoryRepository | None = None):
        self._repo = repo or DocumentCategoryRepository()

    def list_all(self, _actor: User) -> list[DocumentCategory]:
        return self._repo.list_all_ordered()

    def create(self, actor: User, name: str, slug: str | None) -> tuple[Optional[DocumentCategory], Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        raw = (slug or "").strip()
        base = slugify(raw) if raw else slugify(name)
        base = base[:40]
        unique = base
        n = 0
        while self._repo.get_by_slug(unique):
            n += 1
            suffix = f"-{n}"
            unique = (base[: 40 - len(suffix)] + suffix)[:40]
        row = DocumentCategory(name=name.strip(), slug=unique)
        self._repo.create(row)
        return row, None

    def update(self, actor: User, category_id: int, name: str | None) -> tuple[Optional[DocumentCategory], Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        row = self._repo.get_by_id(category_id)
        if not row:
            return None, "Not found"
        if name is not None:
            row.name = name.strip()
        self._repo.save(row)
        return row, None

    def delete(self, actor: User, category_id: int) -> Optional[str]:
        if actor.role != UserRole.ADMIN.value:
            return "Forbidden"
        row = self._repo.get_by_id(category_id)
        if not row:
            return "Not found"
        if self._repo.count_documents_with_slug(row.slug) > 0:
            return "Category is in use by documents"
        self._repo.delete(row)
        return None

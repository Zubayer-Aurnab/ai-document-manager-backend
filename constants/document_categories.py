"""Legacy seed list — categories are stored in `document_categories` (see migration)."""

DOCUMENT_CATEGORY_SLUGS: tuple[str, ...] = (
    "general",
    "legal",
    "hr",
    "finance",
    "operations",
)

DOCUMENT_CATEGORY_ITEMS: list[dict] = [
    {"id": 1, "name": "General", "slug": "general"},
    {"id": 2, "name": "Legal", "slug": "legal"},
    {"id": 3, "name": "HR", "slug": "hr"},
    {"id": 4, "name": "Finance", "slug": "finance"},
    {"id": 5, "name": "Operations", "slug": "operations"},
]

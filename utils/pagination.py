"""Consistent pagination metadata for API responses (Flask-SQLAlchemy `Pagination` or compatible)."""
from __future__ import annotations

import math
from typing import Any


def pagination_meta(paginated: Any) -> dict[str, int]:
    """
    Normalize total / page / per_page / pages for JSON.

    `pages` is always ceil(total / per_page) when total > 0, so clients never get
    a stale or missing page count from the ORM wrapper.
    """
    total = int(getattr(paginated, "total", None) or 0)
    per_page = int(getattr(paginated, "per_page", None) or 20)
    per_page = max(1, min(per_page, 100))
    page = int(getattr(paginated, "page", None) or 1)
    page = max(1, page)
    pages = math.ceil(total / per_page) if total > 0 else 0
    return {"total": total, "page": page, "per_page": per_page, "pages": pages}


def pagination_fields(*, total: int, page: int, per_page: int) -> dict[str, int]:
    """Build pagination fields without a Flask-SQLAlchemy pagination object."""
    per_page = max(1, min(int(per_page or 20), 100))
    page = max(1, int(page or 1))
    total = max(0, int(total))
    pages = math.ceil(total / per_page) if total > 0 else 0
    return {"total": total, "page": page, "per_page": per_page, "pages": pages}

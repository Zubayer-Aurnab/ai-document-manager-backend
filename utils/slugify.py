"""URL-safe slug from human-readable label."""
import re


def slugify(text: str, max_length: int = 40) -> str:
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if not s:
        s = "category"
    return s[:max_length]

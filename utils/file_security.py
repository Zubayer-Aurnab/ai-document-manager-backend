"""Safe file names and extension checks."""
import re
import uuid
from pathlib import Path

from werkzeug.utils import secure_filename


def safe_stored_name(original_name: str, allowed_extensions: frozenset[str]) -> tuple[str, str]:
    """
    Returns (stored_basename_without_path, extension_lower).
    Raises ValueError if extension not allowed.
    """
    name = secure_filename(original_name) or "file"
    ext = Path(name).suffix.lower().lstrip(".")
    if ext not in allowed_extensions:
        raise ValueError(f"File type .{ext or '?'} is not allowed.")
    unique = f"{uuid.uuid4().hex}.{ext}"
    return unique, ext


def is_safe_relative_path(candidate: str) -> bool:
    """Reject path traversal in stored filename lookups."""
    if not candidate or "/" in candidate or "\\" in candidate or ".." in candidate:
        return False
    if not re.match(r"^[a-zA-Z0-9._-]+\.[a-zA-Z0-9]+$", candidate):
        return False
    return True

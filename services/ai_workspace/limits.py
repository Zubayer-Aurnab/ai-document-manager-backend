"""Config-driven limits for workspace context packing."""

from __future__ import annotations

from typing import Any


def _cfg(app_config: dict[str, Any] | Any) -> dict[str, Any]:
    if hasattr(app_config, "get"):
        return app_config  # type: ignore[return-value]
    return {}


def max_documents(app_config: dict[str, Any] | Any) -> int:
    c = _cfg(app_config)
    raw = int(c.get("AI_WORKSPACE_MAX_DOCUMENTS", 6))
    return max(1, min(raw, 12))


def chars_per_document(app_config: dict[str, Any] | Any) -> int:
    c = _cfg(app_config)
    raw = int(c.get("AI_WORKSPACE_CHARS_PER_DOCUMENT", 14_000))
    return max(2_000, min(raw, 40_000))


def max_context_chars(app_config: dict[str, Any] | Any) -> int:
    c = _cfg(app_config)
    raw = int(c.get("AI_WORKSPACE_MAX_CONTEXT_CHARS", 56_000))
    return max(8_000, min(raw, 120_000))

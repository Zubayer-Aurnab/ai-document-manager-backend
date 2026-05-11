"""Parse structured JSON from workspace LLM replies."""

from __future__ import annotations

import json
import re
from typing import Any


def parse_workspace_reply(raw: str) -> tuple[str, list[int]]:
    """
    Expect JSON: {"reply": "...", "source_document_ids": [1,2]}.
    Falls back to full text as reply and empty ids on parse failure.
    """
    text = (raw or "").strip()
    if not text:
        return "", []

    parsed = _try_json_object(text)
    if not parsed:
        return text, []

    reply = parsed.get("reply")
    out_reply = str(reply).strip() if reply is not None else text
    ids_raw = parsed.get("source_document_ids") or parsed.get("sources") or []
    ids: list[int] = []
    if isinstance(ids_raw, list):
        for x in ids_raw:
            try:
                ids.append(int(x))
            except (TypeError, ValueError):
                continue
    seen: set[int] = set()
    uniq: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return out_reply or text, uniq


def _try_json_object(text: str) -> dict[str, Any] | None:
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    brace = re.search(r"\{[\s\S]*\}", text)
    if brace:
        try:
            obj = json.loads(brace.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None

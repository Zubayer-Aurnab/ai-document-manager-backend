"""Call Groq Chat Completions to rank authorized documents for natural-language search."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


def _parse_json_object_from_llm(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        pass
    brace = re.search(r"\{[\s\S]*\}", raw)
    if brace:
        try:
            out = json.loads(brace.group(0))
            return out if isinstance(out, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _compact_doc(c: dict[str, Any]) -> dict[str, Any]:
    """Serialize one candidate for the model (drop empties)."""
    out: dict[str, Any] = {"id": int(c["id"])}
    for key in (
        "title",
        "original_filename",
        "extension",
        "mime_type",
        "category_slug",
        "size_bytes",
        "ai_summary",
        "excerpt",
    ):
        if key not in c:
            continue
        v = c.get(key)
        if v is None or v == "":
            continue
        if key in ("title", "original_filename", "extension", "mime_type", "category_slug", "ai_summary", "excerpt"):
            out[key] = str(v)[:800] if key == "excerpt" else str(v)[:400]
        elif key == "size_bytes":
            try:
                out[key] = int(v)
            except (TypeError, ValueError):
                pass
    return out


class GroqSearchRankingService:
    """Rank document ids using Groq; returns None on any failure (caller may fall back)."""

    def rank_ordered_ids(
        self,
        *,
        api_key: str,
        model: str,
        timeout_sec: int,
        user_query: str,
        candidates: list[dict[str, Any]],
        allowed_ids: set[int],
    ) -> list[int] | None:
        if not api_key or len(candidates) < 2:
            return None

        payload_docs = [_compact_doc(c) for c in candidates]
        user_content = (
            f"User question (natural language): {user_query.strip()[:800]}\n\n"
            "You are given a JSON array of documents the user is already allowed to access. "
            "Each object has at least: id, and may include title, original_filename, extension, mime_type, "
            "size_bytes (file size in bytes), category_slug, ai_summary, excerpt (from document text).\n\n"
            "Documents JSON:\n"
            f"{json.dumps(payload_docs, ensure_ascii=False)}\n\n"
            "Interpret the user's intent (e.g. 'largest image' → pick image-like mime/extension and largest size_bytes; "
            "'company list document' → pick docs whose titles/filenames/excerpts best match that topic).\n\n"
            "Return ONLY a JSON object (no markdown) with this exact shape:\n"
            '{"ordered_ids": [<integer>, ...]}\n'
            "Rules:\n"
            "- ordered_ids: best matches first, only ids from the input list.\n"
            "- Each id at most once; omit documents that do not fit the question.\n"
            "- Use size_bytes numerically when the user asks about largest/smallest/biggest file.\n"
            "- Use mime_type and extension for file type questions (e.g. image, pdf, spreadsheet).\n"
        )

        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You help users find documents they already have access to. "
                        "Reply with a single JSON object only, no other text."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        try:
            resp = requests.post(
                GROQ_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=max(5, min(timeout_sec, 120)),
            )
        except requests.RequestException as e:
            logger.warning("Groq search ranking request failed: %s", e)
            return None

        if resp.status_code >= 400:
            logger.warning("Groq search ranking HTTP %s: %s", resp.status_code, resp.text[:500])
            return None

        try:
            data = resp.json()
            msg = (data.get("choices") or [{}])[0].get("message") or {}
            content = (msg.get("content") or "").strip()
        except (ValueError, KeyError, IndexError) as e:
            logger.warning("Groq search ranking bad response shape: %s", e)
            return None

        parsed = _parse_json_object_from_llm(content)
        if not parsed:
            return None
        raw_ids = parsed.get("ordered_ids")
        if not isinstance(raw_ids, list):
            return None

        out: list[int] = []
        seen: set[int] = set()
        for x in raw_ids:
            try:
                i = int(x)
            except (TypeError, ValueError):
                continue
            if i not in allowed_ids or i in seen:
                continue
            seen.add(i)
            out.append(i)
        return out if out else None

"""Minimal Groq chat-completions client for workspace Q&A."""

from __future__ import annotations

import logging
from typing import Any

import requests
from flask import current_app

from services.groq_search_ranking_service import GROQ_CHAT_URL

logger = logging.getLogger(__name__)


class GroqJsonChatClient:
    """POST JSON body to Groq; returns raw assistant message string or (None, error)."""

    def complete(self, messages: list[dict[str, str]], *, max_tokens: int = 2_000) -> tuple[str | None, str | None]:
        cfg = current_app.config
        api_key = (cfg.get("GROQ_API_KEY") or "").strip()
        if not api_key:
            return None, "AI assistant is not configured (set GROQ_API_KEY on the server)."

        model = str(cfg.get("GROQ_MODEL") or "llama-3.3-70b-versatile")
        timeout = max(10, min(int(cfg.get("GROQ_TIMEOUT_SEC", 45)), 120))
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.25,
            "max_tokens": max_tokens,
        }
        try:
            resp = requests.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=timeout,
            )
        except requests.RequestException as e:
            logger.warning("workspace Groq request failed: %s", e)
            return None, "Could not reach AI service."

        if resp.status_code >= 400:
            logger.warning("workspace Groq HTTP %s: %s", resp.status_code, (resp.text or "")[:500])
            return None, "AI service returned an error."

        try:
            data = resp.json()
            reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            text = str(reply).strip() if reply is not None else ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            logger.warning("workspace Groq bad response: %s", e)
            return None, "Unexpected AI response."

        if not text:
            return None, "Empty response from model."
        return text, None

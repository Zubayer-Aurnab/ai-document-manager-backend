"""Orchestrate retrieval + Groq answer for workspace (multi-document) Q&A."""

from __future__ import annotations

from typing import Any

from flask import current_app

from models.user import User
from services.ai_service import AIService
from services.ai_workspace.context_builder import WorkspaceContextBuilder
from services.ai_workspace.groq_json_client import GroqJsonChatClient
from services.ai_workspace.response_parser import parse_workspace_reply


def _order_sources_by_citation(sources: list[dict[str, Any]], cited: list[int]) -> list[dict[str, Any]]:
    if not cited:
        return sources
    by_id = {s["id"]: s for s in sources}
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for i in cited:
        row = by_id.get(i)
        if row and i not in seen:
            out.append(row)
            seen.add(i)
    for s in sources:
        if s["id"] not in seen:
            out.append(s)
            seen.add(s["id"])
    return out


class WorkspaceQAService:
    """High-level API: one user question → answer + source documents."""

    def __init__(
        self,
        ai: AIService | None = None,
        context_builder: WorkspaceContextBuilder | None = None,
        groq: GroqJsonChatClient | None = None,
    ):
        self._ai = ai or AIService()
        self._context = context_builder or WorkspaceContextBuilder()
        self._groq = groq or GroqJsonChatClient()

    def answer(self, user: User, message: str) -> dict[str, Any]:
        msg = (message or "").strip()
        if len(msg) < 2:
            return {"error": "Message must be at least 2 characters.", "reply": None, "sources": []}

        if len(msg) > 4_000:
            return {"error": "Message is too long (max 4000 characters).", "reply": None, "sources": []}

        ordered_ids, ranked_by_ai, nl_enabled, candidate_limit = self._ai.search_candidate_ids(user, msg)
        if not ordered_ids:
            return {
                "reply": "No documents were found that match your search. Try different keywords or upload relevant files.",
                "sources": [],
                "cited_document_ids": [],
                "ranked_by_ai": ranked_by_ai,
                "natural_language_search": nl_enabled,
                "candidate_limit": candidate_limit,
                "context_documents_used": 0,
            }

        context_text, sources = self._context.build(user, ordered_ids)
        if not context_text.strip():
            return {
                "reply": "Matching documents have no extracted text yet. Open each file on the document page to ensure text was extracted, then try again.",
                "sources": sources,
                "cited_document_ids": [],
                "ranked_by_ai": ranked_by_ai,
                "natural_language_search": nl_enabled,
                "candidate_limit": candidate_limit,
                "context_documents_used": len(sources),
            }

        system = (
            "You are a helpful assistant for an organization's document library. "
            "The user message is a QUESTION. Below is context from multiple documents; each block starts with "
            "--- DOCUMENT_ID: <number>\".\n"
            "Answer using ONLY information in those blocks. If the answer is not contained in the text, say so clearly. "
            "For lists or filters (e.g. companies starting with letters), extract matching rows/lines from the TEXT sections.\n"
            "Respond with a single JSON object ONLY (no markdown outside JSON) in this exact shape:\n"
            '{"reply":"<your answer in plain language, can use short bullet lines inside the string>","source_document_ids":[<ids you used>]}\n'
            "Include every DOCUMENT_ID whose TEXT you relied on for the answer. Sort ids ascending. "
            "Do not invent document ids."
        )

        user_block = f"QUESTION:\n{msg}\n\nDOCUMENT_CONTEXT:\n{context_text}"
        if len(user_block) > 95_000:
            user_block = user_block[:95_000] + "\n… [request truncated]"

        raw, err = self._groq.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_block},
            ],
            max_tokens=2_000,
        )
        if err or raw is None:
            return {
                "error": err or "AI error",
                "reply": None,
                "sources": sources,
                "cited_document_ids": [],
                "ranked_by_ai": ranked_by_ai,
                "natural_language_search": nl_enabled,
                "candidate_limit": candidate_limit,
                "context_documents_used": len(sources),
            }

        reply, cited = parse_workspace_reply(raw)
        id_set = {s["id"] for s in sources}
        cited = [i for i in cited if i in id_set]
        if not cited:
            cited = [s["id"] for s in sources]

        ordered_sources = _order_sources_by_citation(sources, cited)

        return {
            "reply": reply,
            "sources": ordered_sources,
            "cited_document_ids": cited,
            "ranked_by_ai": ranked_by_ai,
            "natural_language_search": nl_enabled,
            "candidate_limit": candidate_limit,
            "context_documents_used": len(sources),
        }

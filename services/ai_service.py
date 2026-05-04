"""Extractive summary, keywords, authorized full-text search, and optional Groq re-ranking."""
import logging
import re
from collections import Counter
from typing import Any

import requests
from flask import current_app
from sqlalchemy.orm import joinedload

from extensions import db
from models.department import Department
from models.document import Document
from models.user import User
from repositories.document_repository import DocumentRepository
from services.document_permission_service import DocumentPermissionService
from services.groq_search_ranking_service import GROQ_CHAT_URL, GroqSearchRankingService
from utils.pagination import pagination_fields

logger = logging.getLogger(__name__)


def _document_tags_list(d: Document) -> list[str]:
    raw = getattr(d, "tags", None)
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()][:25]
    return [str(raw).strip()] if str(raw).strip() else []


class AIService:
    def __init__(
        self,
        doc_repo: DocumentRepository | None = None,
        perm: DocumentPermissionService | None = None,
        groq_ranker: GroqSearchRankingService | None = None,
    ):
        self._docs = doc_repo or DocumentRepository()
        self._perm = perm or DocumentPermissionService()
        self._groq = groq_ranker or GroqSearchRankingService()

    def summarize_text(self, text: str, max_sentences: int = 5) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        picked = sentences[:max_sentences]
        return " ".join(picked) if picked else text[:800]

    def extract_keywords(self, text: str, top_n: int = 15) -> list[dict[str, Any]]:
        text = (text or "").lower()
        tokens = re.findall(r"[a-z0-9_]{3,}", text)
        stop = {
            "the",
            "and",
            "for",
            "that",
            "this",
            "with",
            "from",
            "your",
            "are",
            "was",
            "has",
            "have",
            "not",
            "but",
            "can",
            "will",
            "our",
            "you",
            "all",
            "any",
            "one",
        }
        tokens = [t for t in tokens if t not in stop]
        counts = Counter(tokens).most_common(top_n)
        return [{"keyword": w, "score": c} for w, c in counts]

    def extract_auto_tags(self, text: str, *, title: str | None = None, max_tags: int | None = None) -> list[str]:
        """
        Extractive tags from body (+ title tokens) for upload-time labeling.
        No external API — fast and deterministic.
        """
        try:
            lim = int(current_app.config.get("AI_AUTO_TAG_MAX", 12)) if max_tags is None else int(max_tags)
        except RuntimeError:
            lim = 12
        lim = max(3, min(lim, 25))

        kws = self.extract_keywords(text or "", top_n=min(40, lim * 3))
        tag_stop = {
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "csv",
            "png",
            "jpg",
            "jpeg",
            "page",
            "pages",
            "table",
            "figure",
            "xml",
            "new",
            "old",
            "cover",
            "covers",
            "used",
            "using",
            "also",
            "each",
            "other",
            "such",
            "into",
            "than",
            "then",
            "them",
            "these",
            "those",
            "over",
            "just",
            "only",
            "been",
            "being",
            "were",
            "here",
            "there",
        }
        seen: set[str] = set()
        out: list[str] = []
        for row in kws:
            w = row["keyword"]
            if len(w) < 3 or len(w) > 32 or not w.isalnum() or w.isdigit() or w in tag_stop:
                continue
            label = w.replace("_", " ").title()
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(label[:40])
            if len(out) >= lim:
                return out
        if title and len(out) < lim:
            for tok in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]{2,}", title):
                key = tok.lower()
                if key in seen or key in tag_stop or len(tok) > 32:
                    continue
                seen.add(key)
                out.append(tok.title()[:40])
                if len(out) >= lim:
                    break
        return out

    def process_document_summary(self, document: Document) -> str:
        summary = self.summarize_text(document.extracted_text or "")
        document.ai_summary = summary
        self._docs.save(document)
        return summary

    def process_document_keywords(self, document: Document) -> list[dict[str, Any]]:
        kws = self.extract_keywords(document.extracted_text or "")
        document.ai_keywords = kws
        self._docs.save(document)
        return kws

    def search(self, user: User, query: str, page: int, per_page: int) -> dict[str, Any]:
        q = (query or "").strip()
        if len(q) < 2:
            return {
                "items": [],
                **pagination_fields(total=0, page=page, per_page=per_page),
                "ranked_by_ai": False,
                "candidate_limit": 0,
                "natural_language_search": False,
            }

        cfg = current_app.config
        raw_limit = int(cfg.get("GROQ_AI_SEARCH_CANDIDATE_LIMIT", 40))
        candidate_limit = max(5, min(raw_limit, 100))
        api_key = (cfg.get("GROQ_API_KEY") or "").strip()
        natural_language_search = bool(api_key)

        if api_key:
            kw_cap = min(35, candidate_limit)
            keyword_ids = self._docs.search_authorized_ids(user, q, limit=kw_cap)
            # Only add a recency pool when SQL has no substring hits — otherwise unrelated
            # "recent" docs pollute NL ranking and the UI (merge used to re-append them too).
            if keyword_ids:
                ordered_ids = keyword_ids[:candidate_limit]
            else:
                ordered_ids = self._docs.list_authorized_recent_ids(user, limit=candidate_limit)
        else:
            ordered_ids = self._docs.search_authorized_ids(user, q, limit=candidate_limit)

        total = len(ordered_ids)
        ranked_by_ai = False

        if total == 0:
            return {
                "items": [],
                **pagination_fields(total=0, page=page, per_page=per_page),
                "ranked_by_ai": False,
                "candidate_limit": candidate_limit,
                "natural_language_search": natural_language_search,
            }

        if api_key and total >= 2:
            candidates = self._groq_nl_candidate_payloads(ordered_ids, q)
            allowed = set(ordered_ids)
            ranked = self._groq.rank_ordered_ids(
                api_key=api_key,
                model=str(cfg.get("GROQ_MODEL") or "llama-3.3-70b-versatile"),
                timeout_sec=int(cfg.get("GROQ_TIMEOUT_SEC", 45)),
                user_query=q,
                candidates=candidates,
                allowed_ids=allowed,
            )
            if ranked:
                ordered_ids = self._merge_rank_order(ordered_ids, ranked)
                ranked_by_ai = True
                total = len(ordered_ids)

        start = (page - 1) * per_page
        slice_ids = ordered_ids[start : start + per_page]
        items: list[dict[str, Any]] = []
        for doc_id in slice_ids:
            d = (
                Document.query.options(joinedload(Document.owner))
                .filter(Document.id == doc_id)
                .filter(Document.deleted_at.is_(None))
                .first()
            )
            if not d:
                continue
            perm = self._perm.effective_permission(user, d)
            if not perm:
                continue
            dept_name: str | None = None
            if d.department_id is not None:
                dept = db.session.get(Department, d.department_id)
                dept_name = dept.name if dept else None
            owner = d.owner
            if ranked_by_ai:
                match_reason = "AI natural-language match"
            else:
                match_reason = self._match_reason(d, q)
            items.append(
                {
                    "id": d.id,
                    "title": d.title,
                    "snippet": self._result_snippet(d, q),
                    "summary": (d.ai_summary or "").strip() or None,
                    "tags": _document_tags_list(d),
                    "matched_reason": match_reason,
                    "file_type": self._file_type_label(d),
                    "department": dept_name,
                    "owner": (
                        {"full_name": owner.full_name, "email": owner.email}
                        if owner
                        else None
                    ),
                    "permission": perm,
                }
            )

        return {
            "items": items,
            **pagination_fields(total=total, page=page, per_page=per_page),
            "ranked_by_ai": ranked_by_ai,
            "candidate_limit": candidate_limit,
            "natural_language_search": natural_language_search,
        }

    def _groq_nl_candidate_payloads(self, ids: list[int], query: str) -> list[dict[str, Any]]:
        """Rich metadata + excerpt for Groq natural-language search (no full body)."""
        out: list[dict[str, Any]] = []
        if not ids:
            return out
        rows = (
            Document.query.filter(Document.id.in_(ids))
            .filter(Document.deleted_at.is_(None))
            .all()
        )
        by_id = {r.id: r for r in rows}
        for doc_id in ids:
            d = by_id.get(doc_id)
            if not d:
                continue
            text = (d.extracted_text or d.title or "").strip()
            excerpt = self._snippet(text, query, window=500)
            if len(excerpt.strip()) < 40 and text:
                excerpt = text[:700] + ("…" if len(text) > 700 else "")
            summ = (d.ai_summary or "").strip()
            tag_str = ", ".join(_document_tags_list(d)[:24])
            out.append(
                {
                    "id": d.id,
                    "title": d.title or "",
                    "original_filename": d.original_filename or "",
                    "extension": (d.extension or "").lstrip("."),
                    "mime_type": d.mime_type or "",
                    "size_bytes": int(d.size_bytes) if d.size_bytes is not None else 0,
                    "category_slug": d.category_slug or "",
                    "ai_summary": summ[:600] if summ else "",
                    "tags": tag_str,
                    "excerpt": excerpt,
                }
            )
        return out

    def _result_snippet(self, d: Document, query: str) -> str:
        ql = (query or "").lower().strip()
        if ql:
            tag_hits = [t for t in _document_tags_list(d) if ql in t.lower()]
            if tag_hits:
                return ("Tags: " + ", ".join(tag_hits[:10])).strip()
        base = (d.extracted_text or "") or (d.title or "")
        sn = self._snippet(base, query, window=200)
        if len(sn.strip()) < 24 and base:
            return (base[:280] + ("…" if len(base) > 280 else "")).strip()
        return sn

    @staticmethod
    def _merge_rank_order(original: list[int], ranked: list[int]) -> list[int]:
        """Use Groq's list as the result set: it may omit unrelated docs; do not append them back."""
        if not ranked:
            return original
        seen: set[int] = set()
        out: list[int] = []
        allowed = set(original)
        for i in ranked:
            if i in allowed and i not in seen:
                out.append(i)
                seen.add(i)
        return out

    def _match_reason(self, d: Document, query: str) -> str:
        ql = query.lower().strip()
        if not ql:
            return "Matched"
        if d.title and ql in d.title.lower():
            return "Title match"
        if ql in (d.original_filename or "").lower():
            return "Filename match"
        for t in _document_tags_list(d):
            if ql in t.lower():
                return "Tag match"
        if d.extracted_text and ql in d.extracted_text.lower():
            return "Content match"
        return "Matched"

    def _file_type_label(self, d: Document) -> str:
        ext = (d.extension or "").lstrip(".").upper()
        mime = d.mime_type or ""
        if ext and mime:
            return f"{ext} · {mime}"
        return mime or ext or "—"

    def _snippet(self, text: str, query: str, window: int = 120) -> str:
        low = text.lower()
        idx = low.find(query.lower())
        if idx < 0:
            return text[:window] + ("…" if len(text) > window else "")
        start = max(0, idx - 40)
        end = min(len(text), idx + len(query) + 80)
        sn = text[start:end]
        return ("…" if start > 0 else "") + sn + ("…" if end < len(text) else "")

    def chat_about_document(
        self,
        document: Document,
        message: str,
        history: list[dict[str, Any]] | None,
    ) -> tuple[str | None, str | None]:
        """
        One-shot Groq chat grounded in this document's extracted text and metadata.
        Returns (reply, error_message).
        """
        cfg = current_app.config
        api_key = (cfg.get("GROQ_API_KEY") or "").strip()
        if not api_key:
            return None, "AI assistant is not configured (set GROQ_API_KEY on the server)."

        msg = (message or "").strip()
        if not msg:
            return None, "Message cannot be empty."
        if len(msg) > 4000:
            return None, "Message is too long (max 4000 characters)."

        body_text = (document.extracted_text or "")[:28000]
        tags = ", ".join(_document_tags_list(document))
        summ = ((document.ai_summary or "").strip())[:1500]
        desc = ((getattr(document, "description", None) or "").strip())[:2000]

        context = (
            f"Document title: {document.title or '—'}\n"
            f"Filename: {document.original_filename or '—'}\n"
            f"Type: {(document.extension or '').lstrip('.')} / {document.mime_type or '—'}\n"
            f"Description: {desc or '—'}\n"
            f"Tags: {tags or '—'}\n"
            f"Stored summary (may be empty): {summ or '—'}\n\n"
            f"Extracted document text (truncated; may be partial):\n{body_text or '(no extracted text available)'}"
        )

        system = (
            "You are a helpful assistant. The user is viewing ONE document in their organization. "
            "Answer ONLY using the document context below. If the answer is not in the text, say clearly that "
            "you cannot find it in this document. Be concise and professional. Do not invent facts or cite line numbers "
            "unless they appear in the text.\n\n"
            f"{context}"
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        if history:
            for h in history[-16:]:
                if not isinstance(h, dict):
                    continue
                role = h.get("role")
                content = str(h.get("content") or "").strip()
                if role not in ("user", "assistant") or not content:
                    continue
                messages.append({"role": role, "content": content[:8000]})
        messages.append({"role": "user", "content": msg})

        model = str(cfg.get("GROQ_MODEL") or "llama-3.3-70b-versatile")
        timeout = max(10, min(int(cfg.get("GROQ_TIMEOUT_SEC", 45)), 120))
        body = {
            "model": model,
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": 1400,
        }
        try:
            resp = requests.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=timeout,
            )
        except requests.RequestException as e:
            logger.warning("document AI chat request failed: %s", e)
            return None, "Could not reach AI service."

        if resp.status_code >= 400:
            logger.warning("document AI chat HTTP %s: %s", resp.status_code, (resp.text or "")[:500])
            return None, "AI service returned an error."

        try:
            data = resp.json()
            reply = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
            reply = str(reply).strip() if reply is not None else ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            logger.warning("document AI chat bad response: %s", e)
            return None, "Unexpected AI response."

        if not reply:
            return None, "Empty response from model."
        return reply, None

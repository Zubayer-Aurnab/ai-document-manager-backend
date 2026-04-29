"""Extractive summary, keywords, authorized full-text search, and optional Groq re-ranking."""
import re
from collections import Counter
from typing import Any

from flask import current_app
from sqlalchemy.orm import joinedload

from extensions import db
from models.department import Department
from models.document import Document
from models.user import User
from repositories.document_repository import DocumentRepository
from services.document_permission_service import DocumentPermissionService
from services.groq_search_ranking_service import GroqSearchRankingService
from utils.pagination import pagination_fields


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
            recent_ids = self._docs.list_authorized_recent_ids(user, limit=candidate_limit)
            ordered_ids = self._merge_keyword_and_recent(keyword_ids, recent_ids, candidate_limit)
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

    @staticmethod
    def _merge_keyword_and_recent(keyword_ids: list[int], recent_ids: list[int], max_len: int) -> list[int]:
        """Keyword hits first, then fill with recent authorized docs (deduped)."""
        out: list[int] = []
        seen: set[int] = set()
        for i in keyword_ids:
            if len(out) >= max_len:
                return out
            if i not in seen:
                out.append(i)
                seen.add(i)
        for i in recent_ids:
            if len(out) >= max_len:
                break
            if i not in seen:
                out.append(i)
                seen.add(i)
        return out

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
                    "excerpt": excerpt,
                }
            )
        return out

    def _result_snippet(self, d: Document, query: str) -> str:
        base = (d.extracted_text or "") or (d.title or "")
        sn = self._snippet(base, query, window=200)
        if len(sn.strip()) < 24 and base:
            return (base[:280] + ("…" if len(base) > 280 else "")).strip()
        return sn

    @staticmethod
    def _merge_rank_order(original: list[int], ranked: list[int]) -> list[int]:
        """Place Groq-ranked ids first; append remaining in original order."""
        seen: set[int] = set()
        merged: list[int] = []
        for i in ranked:
            if i in seen:
                continue
            merged.append(i)
            seen.add(i)
        for i in original:
            if i not in seen:
                merged.append(i)
                seen.add(i)
        return merged

    def _match_reason(self, d: Document, query: str) -> str:
        ql = query.lower().strip()
        if not ql:
            return "Matched"
        if d.title and ql in d.title.lower():
            return "Title match"
        if ql in (d.original_filename or "").lower():
            return "Filename match"
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

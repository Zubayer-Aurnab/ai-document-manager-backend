"""Entity to JSON-serializable dicts."""
import hashlib
from typing import Any

from models.company_settings import CompanySettings
from models.department import Department
from models.document import Document
from models.document_category import DocumentCategory
from models.document_share import DocumentShare
from models.notification import Notification
from models.user import User


def gravatar_url(email: str | None, *, size: int = 128) -> str:
    """Gravatar URL: real photo when the address has one, otherwise a generated identicon."""
    normalized = (email or "").strip().lower().encode("utf-8")
    digest = hashlib.md5(normalized).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?s={size}&d=identicon&r=pg"


def owner_summary_dict(u: User | None) -> dict | None:
    """Compact owner payload for document list/detail rows."""
    if u is None:
        return None
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "avatar_url": None,
    }


def user_dict(u: User, *, include_gravatar_avatar: bool = False) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "department_id": u.department_id,
        "is_active": u.is_active,
        "email_verified_at": u.email_verified_at.isoformat() if getattr(u, "email_verified_at", None) else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "avatar_url": gravatar_url(u.email) if include_gravatar_avatar else None,
    }


def department_dict(d: Department) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "description": d.description,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


def document_category_dict(c: DocumentCategory) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def company_settings_dict(c: CompanySettings) -> dict:
    return {
        "id": c.id,
        "company_name": c.company_name,
        "legal_name": c.legal_name,
        "tagline": c.tagline,
        "email": c.email,
        "phone": c.phone,
        "address_line1": c.address_line1,
        "address_line2": c.address_line2,
        "city": c.city,
        "state_region": c.state_region,
        "postal_code": c.postal_code,
        "country": c.country,
        "website": c.website,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def document_dict(
    d: Document,
    permission: str | None = None,
    owner: dict | None = None,
    *,
    share_list_summary: dict | None = None,
) -> dict:
    out = {
        "id": d.id,
        "owner_id": d.owner_id,
        "department_id": d.department_id,
        "title": d.title,
        "description": getattr(d, "description", None),
        "tags": getattr(d, "tags", None),
        "original_filename": d.original_filename,
        "mime_type": d.mime_type,
        "size_bytes": d.size_bytes,
        "extension": d.extension,
        "visibility": d.visibility,
        "category_slug": getattr(d, "category_slug", None),
        "ai_summary": d.ai_summary,
        "ai_keywords": d.ai_keywords,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if getattr(d, "updated_at", None) else None,
    }
    if permission is not None:
        out["permission"] = permission
    if owner is not None:
        out["owner"] = owner
    if share_list_summary is not None:
        out["share_list_summary"] = share_list_summary
    return out


def share_dict(s: DocumentShare) -> dict:
    out = {
        "id": s.id,
        "document_id": s.document_id,
        "shared_with_user_id": s.shared_with_user_id,
        "shared_with_department_id": s.shared_with_department_id,
        "permission": s.permission,
        "expires_at": s.expires_at.isoformat() if getattr(s, "expires_at", None) else None,
        "created_by_id": s.created_by_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    u = getattr(s, "shared_with_user", None)
    if u is not None:
        out["shared_with_user_name"] = u.full_name
        out["shared_with_user_email"] = u.email
    dep = getattr(s, "shared_with_department", None)
    if dep is not None:
        out["shared_with_department_name"] = dep.name
    return out


def notification_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "title": n.title,
        "body": n.body,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "document_id": n.document_id,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


def _activity_action_label(action: str | None) -> str:
    if not action:
        return ""
    parts = [p for p in action.replace(".", " ").split() if p]
    return " ".join(p.replace("_", " ").strip().title() for p in parts)


def _activity_actor_for_log(a) -> dict | None:
    u = getattr(a, "user", None)
    if u is None:
        return None
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "avatar_url": gravatar_url(u.email),
    }


def batch_activity_lookups(logs: list) -> tuple[dict[int, str], dict[int, dict[str, str]]]:
    """Batch-load document titles and user name/email when metadata omits them."""
    from models.document import Document
    from models.user import User

    doc_ids: list[int] = []
    user_ids: list[int] = []
    for a in logs:
        et = (a.entity_type or "").strip()
        eid = a.entity_id
        if not eid:
            continue
        meta = a.metadata_json if isinstance(a.metadata_json, dict) else {}
        if et == "document" and not meta.get("title"):
            doc_ids.append(eid)
        elif et == "user" and not (meta.get("email") or meta.get("name")):
            user_ids.append(eid)

    titles: dict[int, str] = {}
    if doc_ids:
        uniq = list(dict.fromkeys(doc_ids))
        rows = Document.query.filter(Document.id.in_(uniq)).with_entities(Document.id, Document.title).all()
        titles = {r.id: r.title for r in rows}

    users_m: dict[int, dict[str, str]] = {}
    if user_ids:
        uniq = list(dict.fromkeys(user_ids))
        rows = User.query.filter(User.id.in_(uniq)).with_entities(User.id, User.full_name, User.email).all()
        users_m = {r.id: {"full_name": r.full_name, "email": r.email} for r in rows}

    return titles, users_m


def _activity_entity_summary(
    a,
    *,
    document_titles: dict[int, str] | None = None,
    user_entities: dict[int, dict[str, str]] | None = None,
) -> dict[str, Any]:
    meta = a.metadata_json if isinstance(a.metadata_json, dict) else {}
    et = (a.entity_type or "").strip() or None
    eid = a.entity_id
    type_labels = {
        "document": "Document",
        "user": "User",
        "department": "Department",
        "company_settings": "Company settings",
        "document_category": "Category",
    }
    type_label = type_labels.get(et or "", (et or "Unknown").replace("_", " ").title())
    primary = meta.get("title") or meta.get("name") or meta.get("email")
    if et == "document" and eid is not None and document_titles:
        primary = primary or document_titles.get(eid)
    if (
        et == "user"
        and eid is not None
        and user_entities
        and eid in user_entities
        and not primary
    ):
        u = user_entities[eid]
        primary = f"{u['full_name']} · {u['email']}"

    extra: list[dict[str, Any]] = []
    for k in sorted(meta.keys()):
        if k in ("title", "name", "email"):
            continue
        v = meta.get(k)
        if v is None or v == {}:
            continue
        extra.append({"key": str(k), "value": v})
    headline = type_label
    if eid is not None:
        headline = f"{type_label} · #{eid}"
    return {
        "type": et,
        "type_label": type_label,
        "id": eid,
        "headline": headline,
        "primary": primary,
        "extra": extra,
    }


def activity_dict(
    a,
    *,
    document_titles: dict[int, str] | None = None,
    user_entities: dict[int, dict[str, str]] | None = None,
) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "action": a.action,
        "action_label": _activity_action_label(a.action),
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "entity": _activity_entity_summary(
            a,
            document_titles=document_titles,
            user_entities=user_entities,
        ),
        "user": _activity_actor_for_log(a),
        "metadata": a.metadata_json,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }

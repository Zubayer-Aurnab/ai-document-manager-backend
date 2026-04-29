"""Entity to JSON-serializable dicts."""
import hashlib

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
    return out


def share_dict(s: DocumentShare) -> dict:
    return {
        "id": s.id,
        "document_id": s.document_id,
        "shared_with_user_id": s.shared_with_user_id,
        "shared_with_department_id": s.shared_with_department_id,
        "permission": s.permission,
        "expires_at": s.expires_at.isoformat() if getattr(s, "expires_at", None) else None,
        "created_by_id": s.created_by_id,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


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


def activity_dict(a) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "action": a.action,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "metadata": a.metadata_json,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }

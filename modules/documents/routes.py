import json

from flask import request, send_file
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from modules.documents import documents_bp
from schemas.document_schema import DocumentShareSchema, DocumentUpdateSchema, DocumentUploadSchema
from services.ai_service import AIService
from services.activity_log_service import ActivityLogService
from services.document_permission_service import DocumentPermissionService
from services.document_service import DocumentService
from utils.pagination import pagination_meta
from utils.responses import error, success
from utils.serialization import activity_dict, document_dict, owner_summary_dict, share_dict

_docs = DocumentService()
_perm = DocumentPermissionService()
_ai = AIService()
_logs = ActivityLogService()
_upload_schema = DocumentUploadSchema()
_share_schema = DocumentShareSchema()
_update_schema = DocumentUpdateSchema(partial=True)


def _parse_tags_from_form(raw: str | None) -> list[str] | None:
    if not raw or not str(raw).strip():
        return None
    raw = str(raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out = [str(x).strip()[:40] for x in data if str(x).strip()]
            return out[:25] or None
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    parts = [p.strip()[:40] for p in raw.split(",") if p.strip()]
    return parts[:25] or None


def _page():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(page, 1), min(max(per_page, 1), 100)


def _list_filters():
    def s(key: str):
        v = request.args.get(key)
        return v.strip() if v and str(v).strip() else None

    oid = request.args.get("owner_id", type=int)
    return {
        "search": s("q") or s("search"),
        "extension": s("extension"),
        "category_slug": s("category_slug"),
        "visibility": s("visibility"),
        "owner_id": oid,
        "created_from": s("created_from"),
        "created_to": s("created_to"),
    }


@documents_bp.get("")
@jwt_required()
def list_documents():
    scope = (request.args.get("scope") or "my").lower()
    page, per_page = _page()
    filters = _list_filters()
    if scope == "my":
        paginated = _docs.list_my(current_user, page, per_page, filters)
    elif scope == "department":
        dept_id = request.args.get("department_id", type=int)
        paginated, err = _docs.list_department(current_user, dept_id, page, per_page, filters)
        if err:
            status = 400 if err == "department_id is required." else 403
            return error(err, status_code=status)
    elif scope == "shared":
        paginated = _docs.list_shared(current_user, page, per_page, filters)
    elif scope == "admin":
        paginated, err = _docs.list_all_admin(current_user, page, per_page, filters)
        if err:
            return error(err, status_code=403)
    else:
        return error("Invalid scope.", status_code=400)

    items = []
    for d in paginated.items:
        perm = _perm.effective_permission(current_user, d)
        owner = owner_summary_dict(getattr(d, "owner", None))
        items.append(document_dict(d, permission=perm, owner=owner))
    return success(
        data={
            "items": items,
            **pagination_meta(paginated),
        }
    )


@documents_bp.post("")
@jwt_required()
def upload_document():
    if "file" not in request.files:
        return error("Missing file field.", status_code=400)
    file = request.files["file"]
    raw_title = request.form.get("title") or ""
    visibility = request.form.get("visibility") or "department"
    try:
        meta = _upload_schema.load(
            {
                "title": raw_title or None,
                "description": request.form.get("description"),
                "visibility": visibility,
                "category_slug": (request.form.get("category_slug") or "").strip() or None,
            }
        )
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    tags = _parse_tags_from_form(request.form.get("tags"))
    document, err = _docs.upload(
        current_user,
        file,
        meta.get("title") or raw_title,
        meta["visibility"],
        meta.get("category_slug"),
        meta.get("description"),
        tags,
    )
    if err:
        return error(err, status_code=400)
    perm = _perm.effective_permission(current_user, document)
    return success(
        "Document uploaded.",
        {
            "document": document_dict(
                document, permission=perm, owner=owner_summary_dict(getattr(document, "owner", None))
            )
        },
        status_code=201,
    )


@documents_bp.patch("/<int:doc_id>")
@jwt_required()
def patch_document(doc_id: int):
    try:
        body = _update_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    if not body:
        return error("No fields to update.", status_code=400)
    doc, err = _docs.update_metadata(current_user, doc_id, body)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403 if err == "Forbidden" else 400)
    perm = _perm.effective_permission(current_user, doc)
    return success(
        "Document updated.",
        {"document": document_dict(doc, permission=perm, owner=owner_summary_dict(getattr(doc, "owner", None)))},
    )


@documents_bp.get("/<int:doc_id>")
@jwt_required()
def get_document(doc_id: int):
    doc = _docs.get_document(doc_id)
    if not doc:
        return error("Not found.", status_code=404)
    perm = _perm.effective_permission(current_user, doc)
    if not perm:
        return error("Forbidden.", status_code=403)
    return success(
        data={"document": document_dict(doc, permission=perm, owner=owner_summary_dict(getattr(doc, "owner", None)))}
    )


@documents_bp.delete("/<int:doc_id>")
@jwt_required()
def delete_document(doc_id: int):
    err = _docs.soft_delete(current_user, doc_id)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success("Document deleted.")


@documents_bp.get("/<int:doc_id>/preview")
@jwt_required()
def preview_document(doc_id: int):
    delivery, err = _docs.file_delivery(current_user, doc_id, for_download=False)
    if err:
        code = 404 if err == "Not found" else 403 if err == "Forbidden" else 400
        return error(err, status_code=code)
    return send_file(
        delivery["path"],
        mimetype=delivery["mimetype"],
        as_attachment=False,
        download_name=delivery["download_name"],
    )


@documents_bp.get("/<int:doc_id>/download")
@jwt_required()
def download_document(doc_id: int):
    delivery, err = _docs.file_delivery(current_user, doc_id, for_download=True)
    if err:
        code = 404 if err == "Not found" else 403 if err == "Forbidden" else 400
        return error(err, status_code=code)
    return send_file(
        delivery["path"],
        mimetype=delivery["mimetype"],
        as_attachment=True,
        download_name=delivery["download_name"] or "document",
    )


@documents_bp.get("/<int:doc_id>/shares")
@jwt_required()
def list_shares(doc_id: int):
    shares, err = _docs.list_shares(current_user, doc_id)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success(data={"items": [share_dict(s) for s in shares]})


@documents_bp.post("/<int:doc_id>/shares")
@jwt_required()
def add_share(doc_id: int):
    try:
        data = _share_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    sh, err = _docs.share(
        current_user,
        doc_id,
        data.get("shared_with_user_id"),
        data.get("shared_with_department_id"),
        data["permission"],
        data.get("expires_at"),
    )
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403 if err == "Forbidden" else 400)
    return success("Share created.", {"share": share_dict(sh)}, status_code=201)


@documents_bp.delete("/<int:doc_id>/shares/<int:share_id>")
@jwt_required()
def remove_share(doc_id: int, share_id: int):
    err = _docs.revoke_share(current_user, doc_id, share_id)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success("Share removed.")


@documents_bp.post("/<int:doc_id>/ai/summary")
@jwt_required()
def ai_summary(doc_id: int):
    doc = _docs.get_document(doc_id)
    if not doc:
        return error("Not found.", status_code=404)
    if not _perm.require_at_least(current_user, doc, "view"):
        return error("Forbidden.", status_code=403)
    summary = _ai.process_document_summary(doc)
    perm = _perm.effective_permission(current_user, doc)
    return success(
        "Summary generated.",
        {
            "summary": summary,
            "document": document_dict(doc, permission=perm, owner=owner_summary_dict(getattr(doc, "owner", None))),
        },
    )


@documents_bp.post("/<int:doc_id>/ai/keywords")
@jwt_required()
def ai_keywords(doc_id: int):
    doc = _docs.get_document(doc_id)
    if not doc:
        return error("Not found.", status_code=404)
    if not _perm.require_at_least(current_user, doc, "view"):
        return error("Forbidden.", status_code=403)
    kws = _ai.process_document_keywords(doc)
    perm = _perm.effective_permission(current_user, doc)
    return success(
        "Keywords extracted.",
        {
            "keywords": kws,
            "document": document_dict(doc, permission=perm, owner=owner_summary_dict(getattr(doc, "owner", None))),
        },
    )


@documents_bp.get("/<int:doc_id>/activity-logs")
@jwt_required()
def document_activity(doc_id: int):
    doc = _docs.get_document(doc_id)
    if not doc:
        return error("Not found.", status_code=404)
    if not _perm.require_at_least(current_user, doc, "view"):
        return error("Forbidden.", status_code=403)
    page, per_page = _page()
    paginated = _logs.list_paginated(page, per_page, document_id=doc_id)
    return success(
        data={
            "items": [activity_dict(a) for a in paginated.items],
            **pagination_meta(paginated),
        }
    )

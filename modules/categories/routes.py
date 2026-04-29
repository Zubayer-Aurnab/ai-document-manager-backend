from flask import request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from modules.categories import categories_bp
from schemas.document_category_schema import DocumentCategoryCreateSchema, DocumentCategoryUpdateSchema
from services.document_category_service import DocumentCategoryService
from utils.responses import error, success
from utils.serialization import document_category_dict

_service = DocumentCategoryService()
_create = DocumentCategoryCreateSchema()
_update = DocumentCategoryUpdateSchema()


@categories_bp.get("")
@jwt_required()
def list_categories():
    items = _service.list_all(current_user)
    return success(data={"items": [document_category_dict(c) for c in items]})


@categories_bp.post("")
@jwt_required()
def create_category():
    try:
        data = _create.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    row, err = _service.create(current_user, data["name"], data.get("slug"))
    if err:
        return error(err, status_code=403)
    return success("Category created.", {"category": document_category_dict(row)}, status_code=201)


@categories_bp.patch("/<int:category_id>")
@jwt_required()
def update_category(category_id: int):
    try:
        data = _update.load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    row, err = _service.update(current_user, category_id, data.get("name"))
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success("Category updated.", {"category": document_category_dict(row)})


@categories_bp.delete("/<int:category_id>")
@jwt_required()
def delete_category(category_id: int):
    err = _service.delete(current_user, category_id)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        code = 403 if err == "Forbidden" else 400
        return error(err, status_code=code)
    return success("Category deleted.")

from flask import request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from modules.departments import departments_bp
from schemas.department_schema import DepartmentCreateSchema, DepartmentUpdateSchema
from services.department_service import DepartmentService
from utils.responses import error, success
from utils.serialization import department_dict

_service = DepartmentService()
_create = DepartmentCreateSchema()
_update = DepartmentUpdateSchema()


@departments_bp.get("")
@jwt_required()
def list_departments():
    items = _service.list_all(current_user)
    return success(data={"items": [department_dict(d) for d in items]})


@departments_bp.post("")
@jwt_required()
def create_department():
    try:
        data = _create.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    d, err = _service.create(current_user, data["name"], data.get("description"))
    if err:
        code = 403 if err == "Forbidden" else 400
        return error(err, status_code=code)
    return success("Department created.", {"department": department_dict(d)}, status_code=201)


@departments_bp.patch("/<int:dept_id>")
@jwt_required()
def update_department(dept_id: int):
    try:
        data = _update.load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    d, err = _service.update(current_user, dept_id, data.get("name"), data.get("description"))
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success("Department updated.", {"department": department_dict(d)})


@departments_bp.delete("/<int:dept_id>")
@jwt_required()
def delete_department(dept_id: int):
    err = _service.delete(current_user, dept_id)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403 if err == "Forbidden" else 400)
    return success("Department deleted.")

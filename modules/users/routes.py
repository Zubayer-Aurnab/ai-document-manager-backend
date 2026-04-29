from flask import request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from models.user import UserRole
from modules.users import users_bp
from schemas.user_schema import UserCreateSchema, UserUpdateSchema
from services.user_service import UserService
from utils.pagination import pagination_meta
from utils.responses import error, success
from utils.serialization import user_dict

_service = UserService()
_create = UserCreateSchema()
_update = UserUpdateSchema()


def _page():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(page, 1), min(max(per_page, 1), 100)


@users_bp.get("")
@jwt_required()
def list_users():
    page, per_page = _page()
    dept = request.args.get("department_id", type=int)
    search = request.args.get("search", type=str)
    if current_user.role != UserRole.ADMIN.value and dept and dept != current_user.department_id:
        return error("Forbidden.", status_code=403)
    paginated = _service.list_users(current_user, page, per_page, dept, search)
    return success(
        data={
            "items": [user_dict(u) for u in paginated.items],
            **pagination_meta(paginated),
        }
    )


@users_bp.post("")
@jwt_required()
def create_user():
    if current_user.role != UserRole.ADMIN.value:
        return error("Forbidden.", status_code=403)
    try:
        data = _create.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    user, err, email_warning = _service.create_user(current_user, data)
    if err:
        return error(err, status_code=400)
    payload = {"user": user_dict(user)}
    if email_warning:
        payload["email_warning"] = email_warning
    return success(
        "User created. A verification email was sent (or queued) to their address.",
        payload,
        status_code=201,
    )


@users_bp.get("/<int:user_id>")
@jwt_required()
def get_user(user_id: int):
    u = _service.get_user(current_user, user_id)
    if not u:
        return error("Not found.", status_code=404)
    return success(data={"user": user_dict(u)})


@users_bp.patch("/<int:user_id>")
@jwt_required()
def update_user(user_id: int):
    try:
        data = _update.load(request.get_json() or {}, partial=True)
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    u, err = _service.update_user(current_user, user_id, data)
    if err == "Not found":
        return error(err, status_code=404)
    if err:
        return error(err, status_code=403)
    return success("User updated.", {"user": user_dict(u)})

from flask import request
from flask_jwt_extended import current_user, jwt_required

from models.user import UserRole
from modules.logs import logs_bp
from services.activity_log_service import ActivityLogService
from utils.pagination import pagination_meta
from utils.responses import error, success
from utils.serialization import activity_dict

_service = ActivityLogService()


def _page():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(page, 1), min(max(per_page, 1), 100)


@logs_bp.get("")
@jwt_required()
def list_logs():
    if current_user.role != UserRole.ADMIN.value:
        return error("Forbidden.", status_code=403)
    document_id = request.args.get("document_id", type=int)
    page, per_page = _page()
    paginated = _service.list_paginated(page, per_page, document_id=document_id)
    return success(
        data={
            "items": [activity_dict(a) for a in paginated.items],
            **pagination_meta(paginated),
        }
    )

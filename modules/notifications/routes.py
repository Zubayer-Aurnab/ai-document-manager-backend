from flask import request
from flask_jwt_extended import current_user, jwt_required

from modules.notifications import notifications_bp
from services.notification_service import NotificationService
from utils.pagination import pagination_meta
from utils.responses import error, success
from utils.serialization import notification_dict

_service = NotificationService()


def _page():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(page, 1), min(max(per_page, 1), 100)


@notifications_bp.get("")
@jwt_required()
def list_notifications():
    page, per_page = _page()
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    paginated = _service.list_for_user(current_user.id, page, per_page, unread_only)
    return success(
        data={
            "items": [notification_dict(n) for n in paginated.items],
            **pagination_meta(paginated),
        }
    )


@notifications_bp.post("/<int:notif_id>/read")
@jwt_required()
def mark_read(notif_id: int):
    n = _service.mark_read(notif_id, current_user.id)
    if not n:
        return error("Not found.", status_code=404)
    return success("Marked read.", {"notification": notification_dict(n)})


@notifications_bp.post("/read-all")
@jwt_required()
def mark_all_read():
    updated = _service.mark_all_read(current_user.id)
    return success("Marked all read.", {"updated": updated})

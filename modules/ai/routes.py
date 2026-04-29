from flask import request
from flask_jwt_extended import current_user, jwt_required

from modules.ai import ai_bp
from services.ai_service import AIService
from utils.responses import error, success

_ai = AIService()


def _page():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return max(page, 1), min(max(per_page, 1), 50)


@ai_bp.get("/search")
@jwt_required()
def ai_search():
    q = request.args.get("q", "", type=str)
    page, per_page = _page()
    result = _ai.search(current_user, q, page, per_page)
    return success(data=result)

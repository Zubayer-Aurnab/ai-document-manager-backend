from flask import request
from flask_jwt_extended import current_user, jwt_required

from modules.ai import ai_bp
from schemas.workspace_qa_schema import WorkspaceAskSchema
from services.ai_service import AIService
from services.ai_workspace.workspace_qa_service import WorkspaceQAService
from utils.responses import error, success

_ai = AIService()
_workspace_qa = WorkspaceQAService()
_workspace_ask_schema = WorkspaceAskSchema()


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


@ai_bp.post("/workspace-ask")
@jwt_required()
def ai_workspace_ask():
    """Cross-document Q&A: answer from extracted text of top matching authorized documents."""
    payload = request.get_json(silent=True) or {}
    errs = _workspace_ask_schema.validate(payload)
    if errs:
        return error("Validation failed.", errors=errs, status_code=422)
    message = str(payload.get("message") or "")
    result = _workspace_qa.answer(current_user, message)
    if result.get("error"):
        return error(str(result["error"]), status_code=400)
    result.pop("error", None)
    return success("OK.", data=result)

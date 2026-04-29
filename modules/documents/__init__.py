from flask import Blueprint

documents_bp = Blueprint("documents", __name__)

from modules.documents import routes  # noqa: E402, F401

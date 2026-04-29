from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from modules.auth import routes  # noqa: E402, F401

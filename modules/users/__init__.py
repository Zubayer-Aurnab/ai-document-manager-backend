from flask import Blueprint

users_bp = Blueprint("users", __name__)

from modules.users import routes  # noqa: E402, F401

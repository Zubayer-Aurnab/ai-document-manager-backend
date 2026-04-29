from flask import Blueprint

departments_bp = Blueprint("departments", __name__)

from modules.departments import routes  # noqa: E402, F401

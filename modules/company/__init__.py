from flask import Blueprint

company_bp = Blueprint("company", __name__)

from modules.company import routes  # noqa: E402, F401

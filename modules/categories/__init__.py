from flask import Blueprint

categories_bp = Blueprint("categories", __name__)

from modules.categories import routes  # noqa: E402, F401

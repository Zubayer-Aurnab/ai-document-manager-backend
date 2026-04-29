"""Standard JSON API responses."""
from typing import Any

from flask import jsonify


def success(
    message: str = "Action completed successfully.",
    data: Any | None = None,
    status_code: int = 200,
):
    body = jsonify(
        {
            "success": True,
            "message": message,
            "data": data if data is not None else {},
        }
    )
    return body, status_code


def error(message: str = "Something went wrong.", errors: Any | None = None, status_code: int = 400):
    body = {
        "success": False,
        "message": message,
        "errors": errors if errors is not None else {},
    }
    return jsonify(body), status_code

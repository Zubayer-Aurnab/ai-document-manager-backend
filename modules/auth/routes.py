from flask import request
from flask_jwt_extended import create_access_token, current_user, jwt_required
from marshmallow import ValidationError

from modules.auth import auth_bp
from schemas.auth_schema import LoginSchema
from schemas.email_verification_schema import VerifyEmailSchema
from services.auth_service import AuthService
from services.user_email_verification_service import UserEmailVerificationService
from utils.responses import error, success
from utils.serialization import user_dict

_auth = AuthService()
_login_schema = LoginSchema()
_verify_schema = VerifyEmailSchema()
_verification = UserEmailVerificationService()


@auth_bp.post("/verify-email")
def verify_email():
    """Public: complete email verification (admin-created users). Sends welcome email with credentials."""
    try:
        data = _verify_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    ok, message = _verification.complete_with_token(data["token"])
    if not ok:
        return error(message, status_code=400)
    return success(message, {"verified": True})


@auth_bp.post("/login")
def login():
    try:
        data = _login_schema.load(request.get_json() or {})
    except ValidationError as err:
        return error("Validation failed.", errors=err.messages, status_code=422)
    user = _auth.authenticate(data["email"], data["password"])
    if not user:
        if _auth.login_unverified_only(data["email"], data["password"]):
            return error(
                "Please verify your email using the link we sent to your inbox before signing in.",
                status_code=403,
            )
        return error("Invalid credentials.", status_code=401)
    tokens = _auth.build_tokens(user)
    return success(
        "Logged in.",
        {"user": user_dict(user, include_gravatar_avatar=True), **tokens},
    )


@auth_bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    access = create_access_token(identity=str(current_user.id), additional_claims={"role": current_user.role})
    return success("Token refreshed.", {"access_token": access})


@auth_bp.get("/me")
@jwt_required()
def me():
    return success(data={"user": user_dict(current_user, include_gravatar_avatar=True)})

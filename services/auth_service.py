"""Authentication and token issuance."""
from typing import Optional

from flask_jwt_extended import create_access_token, create_refresh_token

from models.user import User
from repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, users: UserRepository | None = None):
        self._users = users or UserRepository()

    def authenticate(self, email: str, password: str) -> Optional[User]:
        user = self._users.get_by_email(email.strip().lower())
        if not user or not user.is_active:
            return None
        if not user.check_password(password):
            return None
        return user

    def build_tokens(self, user: User) -> dict[str, str]:
        identity = str(user.id)
        access = create_access_token(identity=identity, additional_claims={"role": user.role})
        refresh = create_refresh_token(identity=identity)
        return {"access_token": access, "refresh_token": refresh}

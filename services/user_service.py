"""User administration and profile updates."""
from datetime import datetime, timezone
from typing import Any, Optional

from models.user import User, UserRole
from repositories.user_repository import UserRepository
from services.activity_log_service import ActivityLogService


class UserService:
    def __init__(
        self,
        repo: UserRepository | None = None,
        logs: ActivityLogService | None = None,
    ):
        self._repo = repo or UserRepository()
        self._logs = logs or ActivityLogService()

    def list_users(self, actor: User, page: int, per_page: int, department_id: int | None, search: str | None):
        if actor.role != UserRole.ADMIN.value:
            department_id = actor.department_id
        # Admins see inactive accounts in directory UIs (e.g. settings); others only active users.
        active_only = actor.role != UserRole.ADMIN.value
        return self._repo.list_paginated(page, per_page, department_id, search, active_only=active_only)

    def get_user(self, actor: User, user_id: int) -> Optional[User]:
        target = self._repo.get_by_id(user_id)
        if not target:
            return None
        if actor.role == UserRole.ADMIN.value:
            return target
        if target.department_id == actor.department_id:
            return target
        return None

    def create_user(
        self, actor: User, data: dict[str, Any]
    ) -> tuple[Optional[User], Optional[str], Optional[str]]:
        """
        Returns (user, error, email_warning).
        `email_warning` is set when the user was created but the credentials email could not be sent.
        """
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden", None
        if self._repo.get_by_email(data["email"]):
            return None, "Email already registered", None
        user = User(
            email=data["email"].strip().lower(),
            full_name=data["full_name"],
            role=data.get("role", UserRole.USER.value),
            department_id=data.get("department_id"),
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password(data["password"])
        self._repo.create(user)
        self._logs.record(actor.id, "user.created", "user", user.id, {"email": user.email})
        from services.user_invitation_email_service import UserInvitationEmailService

        mail_ok = UserInvitationEmailService().send_account_credentials_email(
            to_email=user.email,
            full_name=user.full_name,
            plaintext_password=data["password"],
        )
        email_warning = None
        if not mail_ok:
            email_warning = (
                "User was created but the sign-in details email could not be sent. "
                "Configure Brevo (BREVO_API_KEY / BREVO_SENDER_EMAIL) or share credentials manually."
            )
        return user, None, email_warning

    def update_user(self, actor: User, user_id: int, data: dict[str, Any]) -> tuple[Optional[User], Optional[str]]:
        target = self._repo.get_by_id(user_id)
        if not target:
            return None, "Not found"
        if actor.role != UserRole.ADMIN.value and actor.id != user_id:
            return None, "Forbidden"
        if actor.role != UserRole.ADMIN.value:
            for k in ("role", "department_id", "is_active"):
                data.pop(k, None)
        # An admin cannot activate/deactivate their own account; another admin can.
        if actor.role == UserRole.ADMIN.value and actor.id == target.id:
            data.pop("is_active", None)
        if actor.role == UserRole.ADMIN.value:
            if "full_name" in data:
                target.full_name = data["full_name"]
            if "department_id" in data:
                target.department_id = data["department_id"]
            if "role" in data:
                target.role = data["role"]
            if "is_active" in data:
                target.is_active = bool(data["is_active"])
        else:
            if "full_name" in data:
                target.full_name = data["full_name"]
        if "password" in data and data["password"]:
            target.set_password(data["password"])
        self._repo.save(target)
        self._logs.record(actor.id, "user.updated", "user", target.id, {})
        return target, None

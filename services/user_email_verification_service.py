"""Issue and complete email verification for admin-created users."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from extensions import db
from models.user import User
from models.user_email_verification import UserEmailVerification
from repositories.user_email_verification_repository import UserEmailVerificationRepository
from repositories.user_repository import UserRepository
from utils.crypto_payload import decrypt_utf8, encrypt_utf8

logger = logging.getLogger(__name__)

VERIFICATION_VALID_DAYS = 2


class UserEmailVerificationService:
    def __init__(
        self,
        verifications: UserEmailVerificationRepository | None = None,
        users: UserRepository | None = None,
        mail: "UserInvitationEmailService | None" = None,
    ):
        self._verifications = verifications or UserEmailVerificationRepository()
        self._users = users or UserRepository()
        from services.user_invitation_email_service import UserInvitationEmailService

        self._mail = mail or UserInvitationEmailService()

    @staticmethod
    def _hash_token(raw: str) -> str:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def start_for_new_user(self, user: User, plaintext_password: str, actor_id: int) -> str | None:
        """
        Create token row, send verification email. Returns error message if email send failed, else None.
        Caller must have persisted user already with email_verified_at unset.
        """
        self._verifications.delete_pending_for_user(user.id)
        raw = secrets.token_urlsafe(32)
        secret = current_app.config["SECRET_KEY"]
        enc = encrypt_utf8(secret, plaintext_password)
        expires = datetime.now(timezone.utc) + timedelta(days=VERIFICATION_VALID_DAYS)
        row = UserEmailVerification(
            user_id=user.id,
            token_hash=self._hash_token(raw),
            encrypted_password=enc,
            expires_at=expires,
        )
        self._verifications.add(row)
        db.session.commit()
        ok = self._mail.send_verification_email(
            to_email=user.email,
            full_name=user.full_name,
            raw_token=raw,
        )
        if not ok:
            return "User was created but the verification email could not be sent. Configure Brevo or resend from support."
        return None

    def complete_with_token(self, raw_token: str) -> tuple[bool, str]:
        """
        Mark user verified, send welcome with password from encrypted row.
        Returns (success, message) for API layer.
        """
        raw = (raw_token or "").strip()
        if not raw:
            return False, "Token is required."
        th = self._hash_token(raw)
        row = self._verifications.get_unused_by_token_hash(th)
        if not row:
            return False, "This link is invalid or has expired. Ask your administrator to resend the invitation."

        user = self._users.get_by_id(row.user_id)
        if not user:
            return False, "User not found."

        secret = current_app.config["SECRET_KEY"]
        try:
            plaintext_password = decrypt_utf8(secret, row.encrypted_password)
        except Exception:
            logger.exception("Failed to decrypt invite payload for user_id=%s", row.user_id)
            return False, "Verification could not be completed. Please contact support."

        now = datetime.now(timezone.utc)
        row.encrypted_password = ""
        user.email_verified_at = now
        row.used_at = now
        db.session.add(user)
        db.session.add(row)
        db.session.commit()

        welcome_ok = self._mail.send_welcome_email(
            to_email=user.email,
            full_name=user.full_name,
            plaintext_password=plaintext_password,
        )
        if not welcome_ok:
            logger.warning("Welcome email failed for user_id=%s (user is verified)", user.id)

        return True, "Your email is verified. Check your inbox for your sign-in details."

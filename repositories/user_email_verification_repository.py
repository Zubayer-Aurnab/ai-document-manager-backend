"""Persistence for email verification tokens."""
from __future__ import annotations

from datetime import datetime, timezone

from extensions import db
from models.user_email_verification import UserEmailVerification


class UserEmailVerificationRepository:
    def delete_pending_for_user(self, user_id: int) -> None:
        UserEmailVerification.query.filter(
            UserEmailVerification.user_id == user_id,
            UserEmailVerification.used_at.is_(None),
        ).delete(synchronize_session=False)

    def add(self, row: UserEmailVerification) -> None:
        db.session.add(row)

    def get_unused_by_token_hash(self, token_hash: str) -> UserEmailVerification | None:
        now = datetime.now(timezone.utc)
        return (
            UserEmailVerification.query.filter(
                UserEmailVerification.token_hash == token_hash,
                UserEmailVerification.used_at.is_(None),
                UserEmailVerification.expires_at > now,
            )
            .first()
        )


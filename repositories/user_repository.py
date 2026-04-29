"""User persistence."""
from typing import Optional

from extensions import db
from models.user import User, UserRole


class UserRepository:
    def get_by_id(self, user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return User.query.filter_by(email=email.lower()).first()

    def list_paginated(
        self,
        page: int,
        per_page: int,
        department_id: Optional[int] = None,
        search: Optional[str] = None,
        *,
        active_only: bool = True,
    ):
        q = User.query
        if active_only:
            q = q.filter(User.is_active.is_(True))
        if department_id is not None:
            q = q.filter(User.department_id == department_id)
        if search:
            like = f"%{search}%"
            q = q.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
        q = q.order_by(User.id.desc())
        return q.paginate(page=page, per_page=per_page, error_out=False)

    def create(self, user: User) -> User:
        db.session.add(user)
        db.session.commit()
        return user

    def save(self, user: User) -> User:
        db.session.add(user)
        db.session.commit()
        return user

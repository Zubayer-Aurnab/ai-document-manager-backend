"""Department CRUD."""
from typing import Optional

from models.department import Department
from models.user import User, UserRole
from repositories.department_repository import DepartmentRepository
from services.activity_log_service import ActivityLogService


class DepartmentService:
    def __init__(
        self,
        repo: DepartmentRepository | None = None,
        logs: ActivityLogService | None = None,
    ):
        self._repo = repo or DepartmentRepository()
        self._logs = logs or ActivityLogService()

    def list_all(self, actor: User) -> list[Department]:
        if actor.role == UserRole.ADMIN.value:
            return self._repo.list_all()
        if actor.department_id:
            d = self._repo.get_by_id(actor.department_id)
            return [d] if d else []
        return []

    def create(self, actor: User, name: str, description: str | None) -> tuple[Optional[Department], Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        if self._repo.get_by_name(name):
            return None, "Department name already exists"
        d = Department(name=name.strip(), description=description)
        self._repo.create(d)
        self._logs.record(actor.id, "department.created", "department", d.id, {"name": name})
        return d, None

    def update(
        self, actor: User, dept_id: int, name: str | None, description: str | None
    ) -> tuple[Optional[Department], Optional[str]]:
        if actor.role != UserRole.ADMIN.value:
            return None, "Forbidden"
        d = self._repo.get_by_id(dept_id)
        if not d:
            return None, "Not found"
        if name:
            other = self._repo.get_by_name(name)
            if other and other.id != d.id:
                return None, "Name conflict"
            d.name = name.strip()
        if description is not None:
            d.description = description
        self._repo.save(d)
        self._logs.record(actor.id, "department.updated", "department", d.id, {})
        return d, None

    def delete(self, actor: User, dept_id: int) -> Optional[str]:
        if actor.role != UserRole.ADMIN.value:
            return "Forbidden"
        d = self._repo.get_by_id(dept_id)
        if not d:
            return "Not found"
        if d.users.count() > 0:
            return "Department has users"
        self._repo.delete(d)
        self._logs.record(actor.id, "department.deleted", "department", dept_id, {})
        return None

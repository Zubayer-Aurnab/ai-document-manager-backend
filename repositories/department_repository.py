"""Department persistence."""
from typing import Optional

from extensions import db
from models.department import Department


class DepartmentRepository:
    def get_by_id(self, dept_id: int) -> Optional[Department]:
        return db.session.get(Department, dept_id)

    def get_by_name(self, name: str) -> Optional[Department]:
        return Department.query.filter(Department.name.ilike(name)).first()

    def list_all(self):
        return Department.query.order_by(Department.name.asc()).all()

    def create(self, department: Department) -> Department:
        db.session.add(department)
        db.session.commit()
        return department

    def save(self, department: Department) -> Department:
        db.session.add(department)
        db.session.commit()
        return department

    def delete(self, department: Department) -> None:
        db.session.delete(department)
        db.session.commit()

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session, joinedload

from ..DTO import EmployeeAuthDTO, EmployeeDTO
from ..Entities import Employee, Permission, Role, RolePermission
from .mappers import to_employee


class EmployeeRepository:
    def __init__(self, session: Session):
        self.session = session

    def _select(self, include_deleted: bool):
        stmt = select(Employee).options(joinedload(Employee.role))
        if not include_deleted:
            stmt = stmt.where(Employee.is_deleted.is_(False))
        return stmt

    def get_by_id(self, employee_id: int, include_deleted: bool = False) -> EmployeeDTO | None:
        e = self.session.scalar(self._select(include_deleted).where(Employee.id == employee_id))
        return to_employee(e) if e else None

    def get_auth_by_login(self, login: str) -> EmployeeAuthDTO | None:
        """Для входа на сайт: сотрудник + хэш пароля. Удалённые не возвращаются."""
        e = self.session.scalar(self._select(False).where(Employee.login == login))
        return EmployeeAuthDTO(employee=to_employee(e), password_hash=e.password_hash) if e else None

    def list_by_role(self, role_name: str, warehouse_id: int | None = None) -> list[EmployeeDTO]:
        stmt = self._select(False).join(Employee.role).where(Role.role_name == role_name)
        if warehouse_id is not None:
            stmt = stmt.where(Employee.warehouse_id == warehouse_id)
        return [to_employee(e) for e in self.session.scalars(stmt.order_by(Employee.last_name))]

    def has_permission(self, employee_id: int, permission_name: str) -> bool:
        stmt = select(
            exists().where(
                Employee.id == employee_id,
                RolePermission.role_id == Employee.role_id,
                Permission.id == RolePermission.permission_id,
                Permission.permission_name == permission_name,
            )
        )
        return bool(self.session.scalar(stmt))

    def create(
        self,
        first_name: str,
        last_name: str,
        login: str,
        password_hash: str,
        warehouse_id: int,
        role_id: int,
    ) -> int:
        e = Employee(
            first_name=first_name,
            last_name=last_name,
            login=login,
            password_hash=password_hash,
            warehouse_id=warehouse_id,
            role_id=role_id,
        )
        self.session.add(e)
        self.session.flush()
        return e.id

    def soft_delete(self, employee_id: int) -> bool:
        result = self.session.execute(
            update(Employee).where(Employee.id == employee_id).values(is_deleted=True)
        )
        return result.rowcount > 0

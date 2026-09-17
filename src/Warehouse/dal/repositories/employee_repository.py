from sqlalchemy import exists, select
from sqlalchemy.orm import contains_eager

from Warehouse.api.dto import EmployeeAuthDTO, EmployeeDTO
from Warehouse.dal.entities import Employee, Permission, Role, RolePermission
from Warehouse.api.mappers import to_employee
from .base_repository import BaseRepository


class EmployeeRepository(BaseRepository[Employee]):
    model = Employee

    def _select(self, include_deleted: bool = False):
        stmt = select(Employee).join(Employee.role).options(contains_eager(Employee.role))
        if not include_deleted:
            stmt = stmt.where(Employee.is_deleted.is_(False))
        return stmt

    # ---------- Чтение ----------

    def get_by_id(self, employee_id: int, include_deleted: bool = False) -> EmployeeDTO | None:
        e = self._one(self._select(include_deleted).where(Employee.id == employee_id))
        return to_employee(e) if e else None

    def get_auth_by_login(self, login: str) -> EmployeeAuthDTO | None:
        """Для входа на сайт: сотрудник + хэш пароля. Удалённые не возвращаются."""
        e = self._one(self._select().where(Employee.login == login))
        return EmployeeAuthDTO(employee=to_employee(e), password_hash=e.password_hash) if e else None

    def login_exists(self, login: str) -> bool:
        """Учитывает и удалённых: логин в БД уникален для всех."""
        return bool(self.session.scalar(select(exists().where(Employee.login == login))))

    def list_by_warehouse(self, warehouse_id: int) -> list[EmployeeDTO]:
        stmt = self._select().where(Employee.warehouse_id == warehouse_id)
        return [to_employee(e) for e in self._all(stmt.order_by(Employee.last_name))]

    def list_by_role(self, role_name: str, warehouse_id: int | None = None) -> list[EmployeeDTO]:
        stmt = self._select().where(Role.role_name == role_name)
        if warehouse_id is not None:
            stmt = stmt.where(Employee.warehouse_id == warehouse_id)
        return [to_employee(e) for e in self._all(stmt.order_by(Employee.last_name))]

    def get_permissions(self, employee_id: int) -> list[str]:
        stmt = (
            select(Permission.permission_name)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Employee, Employee.role_id == RolePermission.role_id)
            .where(Employee.id == employee_id)
            .order_by(Permission.permission_name)
        )
        return list(self.session.scalars(stmt))

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

    # ---------- Запись ----------

    def create(
        self,
        first_name: str,
        last_name: str,
        login: str,
        password_hash: str,
        warehouse_id: int,
        role_id: int,
    ) -> int:
        e = self._add(
            Employee(
                first_name=first_name,
                last_name=last_name,
                login=login,
                password_hash=password_hash,
                warehouse_id=warehouse_id,
                role_id=role_id,
            )
        )
        return e.id

    def set_password_hash(self, employee_id: int, password_hash: str) -> bool:
        return self._update(employee_id, password_hash=password_hash)

    def soft_delete(self, employee_id: int) -> bool:
        return self._update(employee_id, is_deleted=True)


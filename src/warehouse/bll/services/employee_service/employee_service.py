import logging
from collections.abc import Callable

from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.bll.interfaces.employee_service import AbstractEmployeeService
from warehouse.common import PermissionName
from warehouse.common.dto import EmployeeDTO, NewEmployee, RoleDTO, WarehouseDTO
from warehouse.common.exceptions import NotFoundError, ValidationError
from warehouse.common.security import hash_password
from warehouse.dal.unit_of_work import UnitOfWork

MIN_PASSWORD_LENGTH = 8


class EmployeeService(AbstractEmployeeService):
    """Регистрация сотрудников администратором и справочники для её формы."""

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    def list_roles(self, admin_id: int) -> list[RoleDTO]:
        with self._uow_factory() as uow:
            self._admin(uow, admin_id)
            roles = uow.roles.list_all()
            return [RoleDTO(id=role_id, name=name) for role_id, name in sorted(roles.items())]

    def list_warehouses(self, admin_id: int) -> list[WarehouseDTO]:
        with self._uow_factory() as uow:
            self._admin(uow, admin_id)
            return uow.warehouses.list_active()

    def get_warehouse(self, employee_id: int) -> WarehouseDTO:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)
            warehouse = uow.warehouses.get_by_id(actor.employee.warehouse_id)
            if warehouse is None:
                raise NotFoundError(f"Склад №{actor.employee.warehouse_id} не найден")
            return warehouse

    def register(self, admin_id: int, employee: NewEmployee) -> EmployeeDTO:
        first_name = (employee.first_name or "").strip()
        last_name = (employee.last_name or "").strip()
        login = (employee.login or "").strip()
        password = employee.password or ""

        if not first_name or not last_name:
            raise ValidationError("Укажите фамилию и имя сотрудника")
        if not login:
            raise ValidationError("Укажите логин")
        if any(ch.isspace() for ch in login):
            raise ValidationError("В логине не должно быть пробелов")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValidationError(f"Пароль должен быть не короче {MIN_PASSWORD_LENGTH} символов")

        with self._uow_factory() as uow:
            admin = self._admin(uow, admin_id)

            if uow.warehouses.get_by_id(employee.warehouse_id) is None:
                raise NotFoundError(f"Склад №{employee.warehouse_id} не найден")
            if uow.roles.get_name(employee.role_id) is None:
                raise NotFoundError(f"Роль №{employee.role_id} не найдена")
            if uow.employees.login_exists(login):
                raise ValidationError(f"Логин «{login}» уже занят")

            employee_id = uow.employees.create(
                first_name=first_name,
                last_name=last_name,
                login=login,
                password_hash=hash_password(password),
                warehouse_id=employee.warehouse_id,
                role_id=employee.role_id,
            )
            logging.info(
                "Администратор №%s зарегистрировал сотрудника №%s (%s)",
                admin.employee.id,
                employee_id,
                login,
            )
            return uow.employees.get_by_id(employee_id)

    def _admin(self, uow: UnitOfWork, admin_id: int) -> ActorDTO:
        actor = self._access.get_actor(uow, admin_id)
        self._access.require_permission(actor, PermissionName.EMPLOYEE_MANAGE)
        return actor

from warehouse.common.exceptions import AccessDeniedError, NotFoundError
from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.common import PermissionName
from warehouse.dal.unit_of_work import UnitOfWork


class AccessService(AbstractAccessService):
    """Проверка «кто пришёл и что ему можно».

    Вызывается первой строкой из других сервисов внутри их транзакции:

        with self.uow as uow:
            actor = self.access.get_actor(uow, employee_id)
            self.access.require_permission(actor, PermissionName.SHIPMENT_CREATE)
    """

    def get_actor(self, uow: UnitOfWork, employee_id: int) -> ActorDTO:
        employee = uow.employees.get_by_id(employee_id)
        if employee is None:
            raise NotFoundError(f"Сотрудник №{employee_id} не найден или заблокирован")
        permissions = frozenset(uow.employees.get_permissions(employee_id))
        return ActorDTO(employee=employee, permissions=permissions)

    def require_permission(self, actor: ActorDTO, permission: str) -> None:
        if permission not in actor.permissions:
            raise AccessDeniedError("Недостаточно прав для этого действия")

    def require_warehouse(self, actor: ActorDTO, warehouse_id: int) -> None:
        # Администратор — суперпользователь: работает с любым складом.
        if self.is_admin(actor):
            return
        if actor.employee.warehouse_id != warehouse_id:
            raise AccessDeniedError("Доступ запрещён. Вы работаете на другом складе")

    def is_admin(self, actor: ActorDTO) -> bool:
        return PermissionName.EMPLOYEE_MANAGE in actor.permissions

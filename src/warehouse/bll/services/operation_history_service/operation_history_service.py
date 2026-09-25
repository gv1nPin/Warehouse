"""Просмотр журнала операций для администратора."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from warehouse.bll.interfaces.auth_service import AbstractAccessService
from warehouse.bll.interfaces.operation_history_service import AbstractOperationHistoryService
from warehouse.common import PermissionName
from warehouse.common.dto.operation_history import OperationHistoryDTO
from warehouse.common.exceptions import NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork


class OperationHistoryService(AbstractOperationHistoryService):
    """list/get по operation_history. Право: employee:manage."""

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        access: AbstractAccessService,
    ) -> None:
        self._uow_factory = uow_factory
        self.access = access

    def list_operations(
        self,
        employee_id: int,
        *,
        actor_employee_id: int | None = None,
        operation_type: str | None = None,
        entity_name: str | None = None,
        entity_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OperationHistoryDTO]:
        with self._uow_factory() as uow:
            actor = self.access.get_actor(uow, employee_id)
            self.access.require_permission(actor, PermissionName.EMPLOYEE_MANAGE)
            return uow.history.list_operations(
                employee_id=actor_employee_id,
                operation_type=operation_type or None,
                entity_name=entity_name or None,
                entity_id=entity_id,
                since=since,
                until=until,
                limit=limit,
                offset=offset,
            )

    def get_operation(self, employee_id: int, operation_id: int) -> OperationHistoryDTO:
        with self._uow_factory() as uow:
            actor = self.access.get_actor(uow, employee_id)
            self.access.require_permission(actor, PermissionName.EMPLOYEE_MANAGE)
            dto = uow.history.get_by_id(operation_id)
            if dto is None:
                raise NotFoundError(f"Запись журнала №{operation_id} не найдена")
            return dto

    def list_filters(self, employee_id: int) -> dict[str, list[str]]:
        with self._uow_factory() as uow:
            actor = self.access.get_actor(uow, employee_id)
            self.access.require_permission(actor, PermissionName.EMPLOYEE_MANAGE)
            return {
                "operation_types": uow.history.list_operation_types(),
                "entity_names": uow.history.list_entity_names(),
            }

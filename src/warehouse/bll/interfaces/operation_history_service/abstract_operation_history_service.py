"""Интерфейс просмотра журнала операций (только администратор)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from warehouse.common.dto.operation_history import OperationHistoryDTO


class AbstractOperationHistoryService(ABC):
    """Чтение operation_history. Пишет аудит BLL через uow.history.log_operation.

    Транзакцию открывает сам. Доступ — PermissionName.EMPLOYEE_MANAGE (админ).
    """

    @abstractmethod
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
        """Список записей. employee_id — кто запрашивает (проверка прав).

        actor_employee_id — фильтр «кто совершил операцию».
        Нет права -> AccessDeniedError.
        """

    @abstractmethod
    def get_operation(self, employee_id: int, operation_id: int) -> OperationHistoryDTO:
        """Одна запись. Нет -> NotFoundError. Нет права -> AccessDeniedError."""

    @abstractmethod
    def list_filters(self, employee_id: int) -> dict[str, list[str]]:
        """Справочники для фильтров UI: operation_types, entity_names."""

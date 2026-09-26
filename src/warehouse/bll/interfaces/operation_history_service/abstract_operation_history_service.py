from abc import ABC, abstractmethod
from datetime import datetime

from warehouse.common.dto import OperationHistoryDTO


class AbstractOperationHistoryService(ABC):
    """Просмотр журнала операций администратором. Транзакцию открывает сам.

    Пишут в журнал сами сервисы через uow.history.log_operation в своей транзакции.
    Все методы требуют employee:manage, иначе AccessDeniedError.
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
        """Записи журнала, новые сверху. actor_employee_id — кто совершил операцию."""

    @abstractmethod
    def get_operation(self, employee_id: int, operation_id: int) -> OperationHistoryDTO:
        """Одна запись. Нет такой -> NotFoundError."""

    @abstractmethod
    def list_filters(self, employee_id: int) -> dict[str, list[str]]:
        """Значения для фильтров: operation_types и entity_names."""

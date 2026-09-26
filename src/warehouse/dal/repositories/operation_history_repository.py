from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from warehouse.common.dto import OperationHistoryDTO
from warehouse.common.mappers import to_operation
from warehouse.dal.entities import OperationHistory
from .base_repository import BaseRepository

MAX_PAGE = 500


class HistoryRepository(BaseRepository[OperationHistory]):
    """Журнал операций (operation_history): запись аудита и выборки для администратора."""

    model = OperationHistory

    def _select(self):
        return select(OperationHistory).options(
            joinedload(OperationHistory.employee, innerjoin=True)
        )

    # ---------- Чтение ----------

    def get_by_id(self, operation_id: int) -> OperationHistoryDTO | None:
        o = self._one(self._select().where(OperationHistory.id == operation_id))
        return to_operation(o) if o else None

    def list_operations(
        self,
        *,
        employee_id: int | None = None,
        operation_type: str | None = None,
        entity_name: str | None = None,
        entity_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[OperationHistoryDTO]:
        """Новые сверху. None в фильтре — без ограничения."""
        conditions = [
            column == value
            for column, value in (
                (OperationHistory.employee_id, employee_id),
                (OperationHistory.operation_type, operation_type),
                (OperationHistory.entity_name, entity_name),
                (OperationHistory.entity_id, entity_id),
            )
            if value is not None
        ]
        if since is not None:
            conditions.append(OperationHistory.created_at >= since)
        if until is not None:
            conditions.append(OperationHistory.created_at <= until)

        stmt = (
            self._select()
            .where(*conditions)
            .order_by(OperationHistory.created_at.desc(), OperationHistory.id.desc())
            .limit(max(1, min(limit, MAX_PAGE)))
            .offset(max(0, offset))
        )
        return [to_operation(o) for o in self._all(stmt)]

    def list_operation_types(self) -> list[str]:
        stmt = select(OperationHistory.operation_type).distinct().order_by(OperationHistory.operation_type)
        return list(self.session.scalars(stmt))

    def list_entity_names(self) -> list[str]:
        stmt = select(OperationHistory.entity_name).distinct().order_by(OperationHistory.entity_name)
        return list(self.session.scalars(stmt))

    # ---------- Запись ----------

    def log_operation(
        self,
        employee_id: int,
        operation_type: str,
        entity_name: str,
        entity_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Пишет запись в текущую транзакцию: откат операции откатит и запись."""
        self.session.add(
            OperationHistory(
                employee_id=employee_id,
                operation_type=operation_type,
                entity_name=entity_name,
                entity_id=entity_id,
                details=details,
            )
        )

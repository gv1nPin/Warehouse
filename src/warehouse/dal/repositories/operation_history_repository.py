"""Репозиторий журнала операций (аудит)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from warehouse.common.dto.operation_history import OperationHistoryDTO
from warehouse.dal.entities.employee import Employee
from warehouse.dal.entities.operation_history import OperationHistory
from warehouse.dal.repositories.base_repository import BaseRepository


def _to_dto(row: OperationHistory, employee_name: str = "") -> OperationHistoryDTO:
    return OperationHistoryDTO(
        id=row.id,
        employee_id=row.employee_id,
        employee_name=employee_name or f"#{row.employee_id}",
        operation_type=row.operation_type,
        entity_name=row.entity_name,
        entity_id=row.entity_id,
        details=row.details,
        created_at=row.created_at,
    )


class HistoryRepository(BaseRepository[OperationHistory]):
    """Запись и чтение системных логов аудита."""

    model = OperationHistory

    def log_operation(self, data: dict[str, Any]) -> None:
        """Принимает данные аудита от BLL и добавляет в сессию (без commit)."""
        self.session.add(
            OperationHistory(
                employee_id=data["employee_id"],
                operation_type=data["operation_type"],
                entity_name=data["entity_name"],
                entity_id=data.get("entity_id"),
                details=data.get("details"),
            )
        )

    def get_by_id(self, operation_id: int) -> OperationHistoryDTO | None:
        stmt = (
            select(OperationHistory, Employee)
            .outerjoin(Employee, Employee.id == OperationHistory.employee_id)
            .where(OperationHistory.id == operation_id)
        )
        row = self.session.execute(
            stmt.execution_options(populate_existing=True)
        ).first()
        if row is None:
            return None
        op, emp = row
        name = emp.full_name if emp is not None else ""
        return _to_dto(op, name)

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
        """Список записей с фильтрами. Новые сверху."""
        limit = max(1, min(limit, 500))
        offset = max(0, offset)

        stmt = (
            select(OperationHistory, Employee)
            .outerjoin(Employee, Employee.id == OperationHistory.employee_id)
            .order_by(OperationHistory.created_at.desc(), OperationHistory.id.desc())
        )
        if employee_id is not None:
            stmt = stmt.where(OperationHistory.employee_id == employee_id)
        if operation_type:
            stmt = stmt.where(OperationHistory.operation_type == operation_type)
        if entity_name:
            stmt = stmt.where(OperationHistory.entity_name == entity_name)
        if entity_id is not None:
            stmt = stmt.where(OperationHistory.entity_id == entity_id)
        if since is not None:
            stmt = stmt.where(OperationHistory.created_at >= since)
        if until is not None:
            stmt = stmt.where(OperationHistory.created_at <= until)

        stmt = stmt.limit(limit).offset(offset)
        rows = self.session.execute(
            stmt.execution_options(populate_existing=True)
        ).all()
        return [
            _to_dto(op, emp.full_name if emp is not None else "")
            for op, emp in rows
        ]

    def list_operation_types(self) -> list[str]:
        """Уникальные типы операций для фильтра UI."""
        stmt = (
            select(OperationHistory.operation_type)
            .distinct()
            .order_by(OperationHistory.operation_type)
        )
        return list(self.session.scalars(stmt.execution_options(populate_existing=True)))

    def list_entity_names(self) -> list[str]:
        """Уникальные entity_name для фильтра UI."""
        stmt = (
            select(OperationHistory.entity_name)
            .distinct()
            .order_by(OperationHistory.entity_name)
        )
        return list(self.session.scalars(stmt.execution_options(populate_existing=True)))

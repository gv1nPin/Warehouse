"""DTO журнала операций (operation_history)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OperationHistoryDTO:
    """Одна запись аудита для web/BLL (без ORM)."""

    id: int
    employee_id: int
    employee_name: str
    operation_type: str
    entity_name: str
    entity_id: int | None
    details: dict[str, Any] | None
    created_at: datetime

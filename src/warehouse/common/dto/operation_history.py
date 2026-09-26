from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OperationHistoryDTO:
    id: int
    employee_id: int
    employee_name: str
    operation_type: str
    entity_name: str
    entity_id: int | None
    details: dict[str, Any] | None
    created_at: datetime

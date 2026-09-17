from typing import Dict, Any
from warehouse.dal.repositories.base_repository import BaseRepository
from warehouse.dal.entities.operation_history import OperationHistory

class HistoryRepository(BaseRepository):
    def log_operation(self, data: Dict[str, Any]) -> None:
        """Принимает данные аудита от маппера BLL и добавляет в сессию базы данных."""
        db_audit = OperationHistory(
            employee_id=data["employee_id"],
            operation_type=data["operation_type"],
            entity_name=data["entity_name"],
            entity_id=data["entity_id"],
            details=data.get("details")
        )
        self.session.add(db_audit)

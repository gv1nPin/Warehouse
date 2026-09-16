from typing import Dict, Any
from Warehouse.DAL.Entities.OperationHistory import OperationHistory

class HistoryRepository:
    def __init__(self, session):
        self.session = session

    def log_operation(self, data: Dict[str, Any]) -> None:
        """Принимает чистый словарь данных из BLL, маппит его в ORM-модель и добавляет в сессию."""
        db_audit = OperationHistory(
            employee_id=data["employee_id"],
            operation_type=data["operation_type"],
            entity_name=data["entity_name"],
            entity_id=data["entity_id"],
            details=data.get("details")
        )
        self.session.add(db_audit)

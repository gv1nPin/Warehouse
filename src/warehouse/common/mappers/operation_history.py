from warehouse.common.dto import OperationHistoryDTO
from warehouse.dal.entities import OperationHistory


def to_operation(o: OperationHistory) -> OperationHistoryDTO:
    return OperationHistoryDTO(
        id=o.id,
        employee_id=o.employee_id,
        employee_name=o.employee.full_name,
        operation_type=o.operation_type,
        entity_name=o.entity_name,
        entity_id=o.entity_id,
        details=o.details,
        created_at=o.created_at,
    )

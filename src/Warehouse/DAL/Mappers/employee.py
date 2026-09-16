from ..DTO import EmployeeDTO
from ..Entities import Employee


def to_employee(e: Employee) -> EmployeeDTO:
    return EmployeeDTO(
        id=e.id,
        first_name=e.first_name,
        last_name=e.last_name,
        login=e.login,
        role_id=e.role_id,
        role_name=e.role.role_name,
        warehouse_id=e.warehouse_id,
        is_deleted=e.is_deleted,
    )

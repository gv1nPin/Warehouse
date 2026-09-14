from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from Warehouse.DAL.Entities.models import Employee, Role
from Warehouse.DAL.SQLAlchemyUnitOfWork import SQLAlchemyUnitOfWork

class EmployeeRepository:
    def __init__(self, uow: SQLAlchemyUnitOfWork):
        self.uow = uow

    def get_by_id_with_permissions(self, employee_id: int) -> Optional[dict]:
        # Подгружаем связанные сущности через joinedload в синтаксисе select
        stmt = (
            select(Employee)
            .options(joinedload(Employee.role).joinedload(Role.permissions))
            .where(Employee.id == employee_id, Employee.is_deleted == False)
        )
        employee = self.uow.session.scalars(stmt).first()
        
        if not employee:
            return None
            
        permissions_list = []
        if employee.role and employee.role.permissions:
            permissions_list = [p.permission_name for p in employee.role.permissions]
            
        return {
            "id": employee.id,
            "warehouse_id": employee.warehouse_id,
            "permissions": permissions_list
        }

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from Warehouse.DAL.Entities.Employees import Employee
from Warehouse.DAL.Entities.Warehouses import Role
from Warehouse.DAL.UnitOfWork import UnitOfWork

class EmployeeRepository:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def get_by_id_with_permissions(self, employee_id: int) -> Optional[dict]:
        """Загружает сотрудника и собирает плоский список текстовых прав его роли."""
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

    def get_by_login(self, login: str) -> Optional[Employee]:
        """Ищет сотрудника по логину для аутентификации."""
        stmt = select(Employee).where(Employee.login == login, Employee.is_deleted == False)
        return self.uow.session.scalars(stmt).first()  # ИСПРАВЛЕНО: синтаксис закрыт корректно

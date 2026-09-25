from abc import ABC, abstractmethod

from warehouse.common.dto import EmployeeDTO, NewEmployee, RoleDTO, WarehouseDTO


class AbstractEmployeeService(ABC):
    """Регистрация сотрудников администратором и справочники для её формы."""

    @abstractmethod
    def list_roles(self, admin_id: int) -> list[RoleDTO]:
        """Роли для выбора в форме. Нет права employee:manage -> AccessDeniedError."""

    @abstractmethod
    def list_warehouses(self, admin_id: int) -> list[WarehouseDTO]:
        """Склады для выбора в форме. Нет права employee:manage -> AccessDeniedError."""

    @abstractmethod
    def get_warehouse(self, employee_id: int) -> WarehouseDTO:
        """Склад, на котором работает сотрудник."""

    @abstractmethod
    def register(self, admin_id: int, employee: NewEmployee) -> EmployeeDTO:
        """Создаёт сотрудника. Неверные данные или занятый логин -> ValidationError."""

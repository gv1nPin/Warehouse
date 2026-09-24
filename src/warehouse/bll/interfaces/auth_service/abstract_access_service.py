from abc import ABC, abstractmethod
from dataclasses import dataclass

from warehouse.common.dto import EmployeeDTO
from warehouse.dal.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ActorDTO:
    """Сотрудник, который выполняет действие, вместе с правами его роли."""

    employee: EmployeeDTO
    permissions: frozenset[str]


class AbstractAccessService(ABC):
    """Проверка «кто пришёл и что ему можно».

    Транзакцию не открывает: uow передаёт тот, кто вызывает.
    """

    @abstractmethod
    def get_actor(self, uow: UnitOfWork, employee_id: int) -> ActorDTO:
        """Сотрудник и его права. Нет или удалён -> NotFoundError."""

    @abstractmethod
    def require_permission(self, actor: ActorDTO, permission: str) -> None:
        """Нет права -> AccessDeniedError."""

    @abstractmethod
    def require_warehouse(self, actor: ActorDTO, warehouse_id: int) -> None:
        """Склад сотрудника не совпадает -> AccessDeniedError. Администратора не ограничивает."""

    @abstractmethod
    def is_admin(self, actor: ActorDTO) -> bool:
        """Есть ли у сотрудника право employee:manage."""


#Названия папок с маленькой буквы, файлы snake_case
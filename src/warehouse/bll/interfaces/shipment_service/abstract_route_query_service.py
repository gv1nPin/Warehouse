# AbstractRouteQueryService.py

from abc import ABC, abstractmethod

from warehouse.api.dto import StageDTO


class AccessDeniedError(Exception):
    """Сотрудник пытается сделать то, на что у него нет прав."""
    pass


class AbstractRouteQueryService(ABC):
    """
    Абстрактный сервис для ПРОСМОТРА маршрутов (путей/этапов отгрузки).

    Здесь только список методов, которые обязан реализовать наследник.
    Никакой логики внутри нет.
    """

    @abstractmethod
    def list_routes(self, employee_id: int, only_active: bool = False) -> list[StageDTO]:
        """
        Вернуть список маршрутов, доступных сотруднику.

        Параметры:
            employee_id — кто смотрит.
            only_active — True, если нужны только активные маршруты.
        """
        raise NotImplementedError

    @abstractmethod
    def get_route(self, employee_id: int, stage_id: int) -> StageDTO:
        """
        Вернуть ОДИН маршрут (этап) вместе с товарами.
        Доступ проверяется по тем же правилам, что и в list_routes.
        """
        raise NotImplementedError
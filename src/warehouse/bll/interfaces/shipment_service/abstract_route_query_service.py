from abc import ABC, abstractmethod

from warehouse.common.dto import ShipmentDTO, StageDTO


class AbstractRouteQueryService(ABC):
    """Просмотр маршрутов и перевозок.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        routes = route_query.list_routes(employee_id, only_active=True)
        route = route_query.get_route(employee_id, stage_id)
    """

    @abstractmethod
    def list_routes(self, employee_id: int, only_active: bool = False) -> list[StageDTO]:
        """Маршруты, доступные сотруднику.

        Товары (items) не заполняются — для списка они не нужны.
        Сотруднику нечего смотреть -> пустой список, не ошибка.
        """

    @abstractmethod
    def get_route(self, employee_id: int, stage_id: int) -> StageDTO:
        """Один маршрут вместе с товарами (items).

        Нет маршрута -> NotFoundError. Нет прав -> AccessDeniedError.
        """

    @abstractmethod
    def get_shipment_progress(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        """Перевозка целиком: все этапы с товарами.

        Нет перевозки -> NotFoundError. Нет прав -> AccessDeniedError.
        """

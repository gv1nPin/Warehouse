# AbstractShipmentTransitCoordinator.py

from abc import ABC, abstractmethod

from warehouse.api.dto import ShipmentDTO


class AbstractShipmentTransitCoordinator(ABC):
    """
    Абстрактный (недописанный) координатор транзита отгрузок.

    Здесь только «правила игры»: какие методы должны быть у координатора.
    А как именно они работают — описано в классе-наследнике.
    """

    @abstractmethod
    def after_stage_accepted(self, uow, stage_id: int) -> None:
        """
        Что делать ПОСЛЕ того, как этап был принят.

        Параметры:
            uow      — Unit of Work (уже открытая транзакция приёмки).
                       Свою транзакцию этот метод НЕ открывает!
            stage_id — id того этапа, который только что приняли.
        """
        # Это «заглушка». Настоящая логика будет в наследнике.
        raise NotImplementedError

    @abstractmethod
    def get_shipment_progress(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        """
        Показать прогресс отгрузки: сама отгрузка + все её этапы.

        Смотреть разрешено:
          - администратору,
          - или сотруднику склада, который участвует в маршруте
            (например, водитель или приёмщик).
        """
        raise NotImplementedError
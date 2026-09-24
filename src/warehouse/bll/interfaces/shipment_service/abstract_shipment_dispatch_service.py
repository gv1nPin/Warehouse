from abc import ABC, abstractmethod

from warehouse.common.dto import ShipmentDTO, StageDTO


class AbstractShipmentDispatchService(ABC):
    """Резерв, отмена и отправка готового этапа."""

    @abstractmethod
    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Резервирует товары первого этапа на складе отправления.

        Этап -> «Зарезервировано». Не хватает остатка -> InvalidStatusError.
        Нет ни одного документа или позиции -> ValidationError.
        """

    @abstractmethod
    def cancel_shipment(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        """Отменяет перевозку до отправки и возвращает резерв в свободный остаток."""

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Отправляет зарезервированный этап.

        Списывает товар со склада отправления (остаток и резерв),
        этап и перевозка -> «Отправлено».
        """

from abc import ABC, abstractmethod

from warehouse.common.dto import StageDTO


class AbstractShipmentDispatchService(ABC):
    """Диспетчеризация: резерв и отправка уже готового этапа.

    Черновик (маршрут, товары, водитель) собирает ShipmentDraftService —
    этот сервис отвечает только за судьбу готового этапа на складе отправления:
    резервирует остаток и списывает его при отправке.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        dispatch.reserve_stage(employee_id, stage_id)
        dispatch.ship_stage(employee_id, stage_id)

    Отменяет перевозку не этот сервис, а ShipmentCancelService (менеджер).

    Работать можно только с этапами, которые уходят со склада сотрудника.
    """

    @abstractmethod
    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Резервирует товары первого этапа на складе отправления.

        Этап -> «Зарезервировано». Не хватает остатка -> InvalidStatusError.
        Нет ни одного документа или позиции -> ValidationError.
        """

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Отправляет зарезервированный этап.

        Списывает товар со склада отправления (остаток и резерв),
        этап и перевозка -> «Отправлено».
        """

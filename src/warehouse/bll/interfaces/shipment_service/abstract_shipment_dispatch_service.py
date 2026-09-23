from abc import ABC, abstractmethod

from warehouse.api.dto import StageDTO


class AbstractShipmentDispatchService(ABC):
    """Диспетчеризация: резерв и отправка уже готового этапа.

    Черновик (маршрут, товары, водитель) собирает ShipmentDraftService —
    этот сервис отвечает только за судьбу готового этапа на складе отправления:
    резервирует остаток и списывает его при отправке.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        dispatch.reserve_stage(employee_id, stage_id)
        dispatch.ship_stage(employee_id, stage_id)
        # либо, вместо отправки:
        dispatch.cancel_reservation(employee_id, stage_id)

    Работать можно только с этапами, которые уходят со склада сотрудника.
    """

    @abstractmethod
    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Резервирует товары первого этапа на складе отправления.

        Этап -> «Зарезервировано». Не хватает остатка -> InvalidStatusError.
        """

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Отправляет зарезервированный этап.

        Списывает товар со склада отправления (остаток и резерв),
        этап и перевозка -> «Отправлено».
        """

    @abstractmethod
    def cancel_reservation(self, employee_id: int, stage_id: int) -> StageDTO:
        """Отменяет резерв уже зарезервированного этапа.

        Возвращает товар в свободный остаток (снимает reserved_quantity).
        В отличие от delete_draft, запись не удаляет — резерв был реальным
        действием на складе, поэтому этап и перевозка помечаются статусом
        «Отменено», а не стираются. Этап не в «Зарезервировано» -> InvalidStatusError.
        """

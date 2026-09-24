from abc import ABC, abstractmethod

from warehouse.common.dto import ShipmentDTO


class AbstractShipmentCancelService(ABC):
    """Отмена перевозки менеджером или администратором.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        shipment = cancel_service.cancel_shipment(employee_id, shipment_id)
    """

    @abstractmethod
    def cancel_shipment(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        """Отменяет перевозку, пока ни один её этап не отправлен.

        Резерв зарезервированных этапов возвращается в свободный остаток,
        все этапы и перевозка -> «Отменено». Запись не удаляется.
        Груз уже в пути или перевозка завершена -> InvalidStatusError.
        Нет права shipment:cancel -> AccessDeniedError.
        """

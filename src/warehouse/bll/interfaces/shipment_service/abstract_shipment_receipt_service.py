from abc import ABC, abstractmethod
from decimal import Decimal

from warehouse.common.dto import StageDTO, StageItemDTO


class AbstractShipmentReceiptService(ABC):
    """Приёмка груза на складе назначения.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        incoming = receipt.get_incoming(employee_id)
        receipt.enter_actual_quantity(employee_id, item_id, Decimal("10.5"))
        stage = receipt.accept_stage(employee_id, stage_id)
    """

    @abstractmethod
    def get_incoming(self, employee_id: int) -> list[StageDTO]:
        """Этапы в статусе «Отправлено», которые едут на склад сотрудника.

        Товары (items) заполнены — по ним сразу вносят факт.
        """

    @abstractmethod
    def enter_actual_quantity(
        self,
        employee_id: int,
        item_id: int,
        quantity: Decimal,
        comment: str | None = None,
    ) -> None:
        """Вносит фактически принятое количество по позиции этапа.

        Количество расходится с документом -> комментарий обязателен.
        """

    @abstractmethod
    def check_discrepancies(self, employee_id: int, stage_id: int) -> list[StageItemDTO]:
        """Позиции без факта или с расхождением. Ничего не меняет."""

    @abstractmethod
    def accept_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Закрывает приёмку этапа.

        Приходует остатки на склад и двигает перевозку дальше по маршруту.
        Возвращает этап в финальном статусе.
        """

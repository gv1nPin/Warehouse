from abc import ABC, abstractmethod
from typing import List, Optional
from warehouse.api.dto import StageDTO, StageItemDTO


class AbstractShipmentReceiptService(ABC):
    """Абстрактный интерфейс для сервиса приемки поставок на складе."""

    @abstractmethod
    def get_incoming(self, employee_id: int) -> List[StageDTO]:
        """Получить список этапов, едущих на склад сотрудника в статусе 'Отправлено'."""
        pass

    @abstractmethod
    def enter_actual_quantity(
        self, 
        employee_id: int, 
        item_id: int, 
        quantity: float, 
        comment: Optional[str] = None
    ) -> None:
        """Внести фактическое количество товара по позиции этапа."""
        pass

    @abstractmethod
    def check_discrepancies(self, employee_id: int, stage_id: int) -> List[StageItemDTO]:
        """Возвращает позиции StageItems без факта или с несовпадением документов."""
        pass

    @abstractmethod
    def accept_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Окончательно принять этап поставки на склад с оприходованием остатков."""
        pass

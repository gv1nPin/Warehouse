from abc import ABC, abstractmethod

from warehouse.common.dto import StockItemDTO


class AbstractStockQueryService(ABC):
    """Остатки склада сотрудника. Транзакцию открывает сам."""

    @abstractmethod
    def list_stock(self, employee_id: int) -> list[StockItemDTO]:
        """Все остатки своего склада, включая полностью зарезервированные.

        Нет ни одного из прав shipment:create / :dispatch / :accept -> AccessDeniedError.
        """

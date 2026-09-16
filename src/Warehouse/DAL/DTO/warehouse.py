from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class WarehouseDTO:
    id: int
    title: str
    address: str


@dataclass(frozen=True, slots=True)
class StockItemDTO:
    warehouse_id: int
    product_id: int
    article_number: str
    product_name: str
    measurement_name: str
    quantity: Decimal
    reserved_quantity: Decimal

    @property
    def available(self) -> Decimal:
        """Сколько можно отправить: всё, что лежит, минус зарезервированное."""
        return self.quantity - self.reserved_quantity

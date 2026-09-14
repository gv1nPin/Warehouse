from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, joinedload

from ..DTO import StockItemDTO, WarehouseDTO
from ..Entities import Product, StockOnWarehouse, Warehouse
from .mappers import to_stock_item, to_warehouse


class WarehouseRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, warehouse_id: int) -> WarehouseDTO | None:
        w = self.session.get(Warehouse, warehouse_id)
        return to_warehouse(w) if w and not w.is_deleted else None

    def list_active(self) -> list[WarehouseDTO]:
        stmt = select(Warehouse).where(Warehouse.is_deleted.is_(False)).order_by(Warehouse.title)
        return [to_warehouse(w) for w in self.session.scalars(stmt)]

    def create(self, title: str, address: str) -> int:
        w = Warehouse(title=title, address=address)
        self.session.add(w)
        self.session.flush()
        return w.id


class StockRepository:
    """Остатки товаров на складах (Inventory)."""

    def __init__(self, session: Session):
        self.session = session

    def _select(self):
        return (
            select(StockOnWarehouse)
            .join(StockOnWarehouse.product)
            .options(joinedload(StockOnWarehouse.product).joinedload(Product.measurement))
            .where(Product.is_deleted.is_(False))
        )

    def list_available(self, warehouse_id: int) -> list[StockItemDTO]:
        """Товары, которые есть на складе и не зарезервированы полностью."""
        stmt = (
            self._select()
            .where(
                StockOnWarehouse.warehouse_id == warehouse_id,
                StockOnWarehouse.quantity > StockOnWarehouse.reserved_quantity,
            )
            .order_by(Product.product_name)
        )
        return [to_stock_item(s) for s in self.session.scalars(stmt)]

    def get_many(self, warehouse_id: int, product_ids: Iterable[int]) -> dict[int, StockItemDTO]:
        stmt = self._select().where(
            StockOnWarehouse.warehouse_id == warehouse_id,
            StockOnWarehouse.product_id.in_(list(product_ids)),
        )
        return {s.product_id: to_stock_item(s) for s in self.session.scalars(stmt)}

    def change(
        self,
        warehouse_id: int,
        product_id: int,
        quantity_delta: Decimal = Decimal(0),
        reserved_delta: Decimal = Decimal(0),
    ) -> bool:
        """Атомарно меняет остаток и резерв. Уйти в минус не даст ограничение в БД.

        Возвращает False, если такой строки остатка нет.
        """
        result = self.session.execute(
            update(StockOnWarehouse)
            .where(
                StockOnWarehouse.warehouse_id == warehouse_id,
                StockOnWarehouse.product_id == product_id,
            )
            .values(
                quantity=StockOnWarehouse.quantity + quantity_delta,
                reserved_quantity=StockOnWarehouse.reserved_quantity + reserved_delta,
                last_updated=func.now(),
            )
        )
        return result.rowcount > 0

    def add_quantity(self, warehouse_id: int, product_id: int, amount: Decimal) -> None:
        """Приход товара: создаёт строку остатка, если её ещё нет."""
        stmt = insert(StockOnWarehouse).values(
            warehouse_id=warehouse_id, product_id=product_id, quantity=amount
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[StockOnWarehouse.warehouse_id, StockOnWarehouse.product_id],
            set_={
                "quantity": StockOnWarehouse.quantity + stmt.excluded.quantity,
                "last_updated": func.now(),
            },
        )
        self.session.execute(stmt)

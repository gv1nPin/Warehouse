from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import contains_eager, joinedload

from Warehouse.api.dto import StockItemDTO
from Warehouse.dal.entities import Product, StockOnWarehouse
from Warehouse.api.mappers import to_stock_item
from .base_repository import BaseRepository


class StockRepository(BaseRepository[StockOnWarehouse]):
    """Остатки товаров на складах (Inventory). Ключ записи — (warehouse_id, product_id)."""

    model = StockOnWarehouse

    def _select(self, warehouse_id: int, for_update: bool = False):
        stmt = (
            select(StockOnWarehouse)
            .join(StockOnWarehouse.product)
            .options(
                contains_eager(StockOnWarehouse.product).joinedload(
                    Product.measurement, innerjoin=True
                )
            )
            .where(StockOnWarehouse.warehouse_id == warehouse_id, Product.is_deleted.is_(False))
        )
        if for_update:
            # Блокируем строки остатков до конца транзакции, чтобы два кладовщика
            # не зарезервировали один и тот же товар одновременно.
            stmt = stmt.with_for_update(of=StockOnWarehouse)
        return stmt

    # ---------- Чтение ----------

    def get(self, warehouse_id: int, product_id: int, for_update: bool = False) -> StockItemDTO | None:
        stmt = self._select(warehouse_id, for_update).where(StockOnWarehouse.product_id == product_id)
        s = self._one(stmt)
        return to_stock_item(s) if s else None

    def get_many(
        self, warehouse_id: int, product_ids: Iterable[int], for_update: bool = False
    ) -> dict[int, StockItemDTO]:
        """{product_id: остаток}. Товаров, которых на складе нет, в ответе не будет."""
        stmt = self._select(warehouse_id, for_update).where(
            StockOnWarehouse.product_id.in_(list(product_ids))
        )
        return {s.product_id: to_stock_item(s) for s in self._all(stmt)}

    def list_by_warehouse(self, warehouse_id: int) -> list[StockItemDTO]:
        stmt = self._select(warehouse_id).order_by(Product.product_name)
        return [to_stock_item(s) for s in self._all(stmt)]

    def list_available(self, warehouse_id: int) -> list[StockItemDTO]:
        """Товары, которые есть на складе и не зарезервированы полностью."""
        stmt = (
            self._select(warehouse_id)
            .where(StockOnWarehouse.quantity > StockOnWarehouse.reserved_quantity)
            .order_by(Product.product_name)
        )
        return [to_stock_item(s) for s in self._all(stmt)]

    # ---------- Запись ----------

    def change(
        self,
        warehouse_id: int,
        product_id: int,
        quantity_delta: Decimal = Decimal(0),
        reserved_delta: Decimal = Decimal(0),
    ) -> bool:
        """Атомарно меняет остаток и резерв (дельты могут быть отрицательными).

        Хватает ли товара, проверяет BLL (сначала get(..., for_update=True)).
        В скрипте создания таблиц CHECK-ограничений на остатки нет.
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

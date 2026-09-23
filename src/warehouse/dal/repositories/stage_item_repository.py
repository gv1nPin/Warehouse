from collections.abc import Iterable
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from warehouse.common.dto import NewStageItem, StageItemDTO
from warehouse.dal.entities import Product, StageItem
from warehouse.common.mappers import to_stage_item
from .base_repository import BaseRepository


class StageItemRepository(BaseRepository[StageItem]):
    """Товары внутри этапа (StageItems): сколько по документам и сколько приняли по факту."""

    model = StageItem

    def _select(self):
        return select(StageItem).options(
            joinedload(StageItem.product).joinedload(Product.measurement)
        )

    # ---------- Чтение ----------

    def get_by_id(self, item_id: int) -> StageItemDTO | None:
        i = self._one(self._select().where(StageItem.id == item_id))
        return to_stage_item(i) if i else None

    def list_by_stage(self, stage_id: int) -> list[StageItemDTO]:
        stmt = self._select().where(StageItem.stage_id == stage_id).order_by(StageItem.id)
        return [to_stage_item(i) for i in self._all(stmt)]

    def count_unfilled(self, stage_id: int) -> int:
        """Сколько позиций этапа ещё без фактического количества (actual_quantity IS NULL)."""
        stmt = select(func.count()).where(
            StageItem.stage_id == stage_id, StageItem.actual_quantity.is_(None)
        )
        return self.session.scalar(stmt) or 0

    # ---------- Запись ----------

    def add(
        self, stage_id: int, product_id: int, document_quantity: Decimal, comment: str | None = None
    ) -> int:
        """В одном этапе товар может быть только один раз (уникальность в БД)."""
        item = StageItem(
            stage_id=stage_id,
            product_id=product_id,
            document_quantity=document_quantity,
            comment=comment,
        )
        return self._add(item).id

    def add_many(self, stage_id: int, items: Iterable[NewStageItem]) -> None:
        self.session.add_all(
            StageItem(stage_id=stage_id, product_id=i.product_id, document_quantity=i.quantity)
            for i in items
        )
        self.session.flush()

    def set_document_quantity(self, item_id: int, document_quantity: Decimal) -> bool:
        return self._update(item_id, document_quantity=document_quantity)

    def set_actual_quantity(
        self, item_id: int, actual_quantity: Decimal, comment: str | None = None
    ) -> bool:
        """Фактически принятое количество по позиции (при приёмке)."""
        return self._update(item_id, actual_quantity=actual_quantity, comment=comment)

    def delete(self, item_id: int) -> bool:
        return self._delete(item_id)

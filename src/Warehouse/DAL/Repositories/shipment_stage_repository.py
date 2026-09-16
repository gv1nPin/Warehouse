from collections.abc import Collection
from datetime import datetime

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import joinedload, selectinload

from ..DTO import StageDTO
from ..Entities import Product, Shipment, ShipmentStage, StageItem
from ..Mappers import to_stage
from .base_repository import BaseRepository

# Что подгружать вместе с этапом, чтобы маппер не делал лишних запросов.
STAGE_OPTIONS = (
    joinedload(ShipmentStage.shipment).joinedload(Shipment.status),
    joinedload(ShipmentStage.status),
    joinedload(ShipmentStage.from_warehouse),
    joinedload(ShipmentStage.to_warehouse),
    joinedload(ShipmentStage.driver),
)

ITEMS_OPTION = (
    selectinload(ShipmentStage.items)
    .joinedload(StageItem.product)
    .joinedload(Product.measurement)
)


class ShipmentStageRepository(BaseRepository[ShipmentStage]):
    """Этапы отгрузки (ShipmentStages) — «пути» из склада A в склад B."""

    model = ShipmentStage

    def _list(
        self, *conditions, status_ids: Collection[int] | None, with_items: bool
    ) -> list[StageDTO]:
        stmt = select(ShipmentStage).where(*conditions).options(*STAGE_OPTIONS)
        if status_ids is not None:
            stmt = stmt.where(ShipmentStage.status_id.in_(status_ids))
        if with_items:
            stmt = stmt.options(ITEMS_OPTION)
        stmt = stmt.order_by(ShipmentStage.shipment_id.desc(), ShipmentStage.stage_order)
        return [to_stage(st, with_items) for st in self._all(stmt)]

    # ---------- Чтение ----------

    def get_by_id(self, stage_id: int, with_items: bool = True) -> StageDTO | None:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id).options(*STAGE_OPTIONS)
        if with_items:
            stmt = stmt.options(ITEMS_OPTION)
        st = self._one(stmt)
        return to_stage(st, with_items) if st else None

    def get_by_order(
        self, shipment_id: int, stage_order: int, with_items: bool = False
    ) -> StageDTO | None:
        """Этап по номеру. Следующий этап: get_by_order(shipment_id, stage.stage_order + 1)."""
        stmt = (
            select(ShipmentStage)
            .where(ShipmentStage.shipment_id == shipment_id, ShipmentStage.stage_order == stage_order)
            .options(*STAGE_OPTIONS)
        )
        if with_items:
            stmt = stmt.options(ITEMS_OPTION)
        st = self._one(stmt)
        return to_stage(st, with_items) if st else None

    def list_by_shipment(self, shipment_id: int, with_items: bool = False) -> list[StageDTO]:
        return self._list(
            ShipmentStage.shipment_id == shipment_id, status_ids=None, with_items=with_items
        )

    def list_all(
        self, status_ids: Collection[int] | None = None, with_items: bool = False
    ) -> list[StageDTO]:
        """Администратор: все пути."""
        return self._list(status_ids=status_ids, with_items=with_items)

    def list_for_warehouse(
        self,
        warehouse_id: int,
        status_ids: Collection[int] | None = None,
        with_items: bool = False,
    ) -> list[StageDTO]:
        """Кладовщик: пути, которые уходят с его склада или приходят на него."""
        return self._list(
            or_(
                ShipmentStage.from_warehouse_id == warehouse_id,
                ShipmentStage.to_warehouse_id == warehouse_id,
            ),
            status_ids=status_ids,
            with_items=with_items,
        )

    def list_incoming(
        self, warehouse_id: int, status_ids: Collection[int], with_items: bool = False
    ) -> list[StageDTO]:
        """Пути, которые едут НА склад (для приёмки)."""
        return self._list(
            ShipmentStage.to_warehouse_id == warehouse_id,
            status_ids=status_ids,
            with_items=with_items,
        )

    def list_outgoing(
        self, warehouse_id: int, status_ids: Collection[int] | None = None, with_items: bool = False
    ) -> list[StageDTO]:
        """Пути, которые уходят СО склада (для отправки)."""
        return self._list(
            ShipmentStage.from_warehouse_id == warehouse_id,
            status_ids=status_ids,
            with_items=with_items,
        )

    def list_for_driver(
        self, driver_id: int, status_ids: Collection[int] | None = None, with_items: bool = False
    ) -> list[StageDTO]:
        """Водитель: его пути."""
        return self._list(
            ShipmentStage.driver_id == driver_id, status_ids=status_ids, with_items=with_items
        )

    def any_with_status(self, shipment_id: int, status_ids: Collection[int]) -> bool:
        """Есть ли у отгрузки хоть один этап с таким статусом (например, «с расхождениями»)."""
        stmt = select(
            exists().where(
                ShipmentStage.shipment_id == shipment_id,
                ShipmentStage.status_id.in_(status_ids),
            )
        )
        return bool(self.session.scalar(stmt))

    # ---------- Запись ----------

    def create(
        self,
        shipment_id: int,
        stage_order: int,
        from_warehouse_id: int,
        to_warehouse_id: int,
        status_id: int,
        driver_id: int | None = None,
    ) -> int:
        stage = ShipmentStage(
            shipment_id=shipment_id,
            stage_order=stage_order,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            status_id=status_id,
            driver_id=driver_id,
        )
        return self._add(stage).id

    def set_status(
        self,
        stage_id: int,
        status_id: int,
        *,
        sent_at: datetime | None = None,
        received_at: datetime | None = None,
        acceptor_id: int | None = None,
    ) -> bool:
        """Меняет статус этапа. Переданные даты и приёмщик записываются, None не трогается."""
        values = {"status_id": status_id}
        if sent_at is not None:
            values["sent_at"] = sent_at
        if received_at is not None:
            values["received_at"] = received_at
        if acceptor_id is not None:
            values["acceptor_id"] = acceptor_id
        return self._update(stage_id, **values)

    def assign_driver(self, stage_id: int, driver_id: int | None) -> bool:
        return self._update(stage_id, driver_id=driver_id)

    def delete(self, stage_id: int) -> bool:
        """Товары этапа удалятся каскадом."""
        return self._delete(stage_id)

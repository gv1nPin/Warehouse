from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from ..constants import ACTIVE_STATUSES
from ..DTO import NewStage, RouteDTO, ShipmentDTO
from ..Entities import Product, Shipment, ShipmentStage, StageItem, Status
from .mappers import to_route, to_shipment

_ROUTE_OPTIONS = (
    joinedload(ShipmentStage.shipment).joinedload(Shipment.status),
    joinedload(ShipmentStage.status),
    joinedload(ShipmentStage.from_warehouse),
    joinedload(ShipmentStage.to_warehouse),
    joinedload(ShipmentStage.driver),
)

_ITEMS_OPTION = (
    selectinload(ShipmentStage.items)
    .joinedload(StageItem.product)
    .joinedload(Product.measurement)
)


class ShipmentRepository:
    """Отгрузки (Shipments) и их пути (ShipmentStages)."""

    def __init__(self, session: Session):
        self.session = session

    # ---------- Запись ----------

    def create(
        self,
        creator_id: int,
        planned_date: date,
        status_id: int,
        stages: Sequence[NewStage],
    ) -> int:
        """Создаёт отгрузку со всеми этапами и товарами. Этапы нумеруются по порядку."""
        shipment = Shipment(creator_id=creator_id, planned_date=planned_date, status_id=status_id)
        for order, stage in enumerate(stages, start=1):
            shipment.stages.append(
                ShipmentStage(
                    stage_order=order,
                    status_id=status_id,
                    from_warehouse_id=stage.from_warehouse_id,
                    to_warehouse_id=stage.to_warehouse_id,
                    driver_id=stage.driver_id,
                    items=[
                        StageItem(product_id=i.product_id, document_quantity=i.quantity)
                        for i in stage.items
                    ],
                )
            )
        self.session.add(shipment)
        self.session.flush()
        return shipment.id

    def set_shipment_status(self, shipment_id: int, status_id: int) -> bool:
        result = self.session.execute(
            update(Shipment).where(Shipment.id == shipment_id).values(status_id=status_id)
        )
        return result.rowcount > 0

    def set_stage_status(
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
        result = self.session.execute(
            update(ShipmentStage).where(ShipmentStage.id == stage_id).values(**values)
        )
        return result.rowcount > 0

    def assign_driver(self, stage_id: int, driver_id: int | None) -> bool:
        result = self.session.execute(
            update(ShipmentStage).where(ShipmentStage.id == stage_id).values(driver_id=driver_id)
        )
        return result.rowcount > 0

    def set_actual_quantity(
        self, item_id: int, actual_quantity: Decimal, comment: str | None = None
    ) -> bool:
        """Фактически принятое количество по позиции (при приёмке)."""
        result = self.session.execute(
            update(StageItem)
            .where(StageItem.id == item_id)
            .values(actual_quantity=actual_quantity, comment=comment)
        )
        return result.rowcount > 0

    # ---------- Чтение ----------

    def get_by_id(self, shipment_id: int) -> ShipmentDTO | None:
        stmt = (
            select(Shipment)
            .where(Shipment.id == shipment_id)
            .options(
                joinedload(Shipment.status),
                joinedload(Shipment.creator),
                selectinload(Shipment.stages).options(*_ROUTE_OPTIONS, _ITEMS_OPTION),
            )
        )
        sh = self.session.scalar(stmt)
        return to_shipment(sh) if sh else None

    def get_route(self, stage_id: int, with_items: bool = True) -> RouteDTO | None:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id).options(*_ROUTE_OPTIONS)
        if with_items:
            stmt = stmt.options(_ITEMS_OPTION)
        st = self.session.scalar(stmt)
        return to_route(st, with_items) if st else None

    def _list_routes(self, *conditions, active_only: bool, with_items: bool) -> list[RouteDTO]:
        stmt = select(ShipmentStage).where(*conditions).options(*_ROUTE_OPTIONS)
        if active_only:
            stmt = stmt.where(ShipmentStage.status.has(Status.status_name.in_(ACTIVE_STATUSES)))
        if with_items:
            stmt = stmt.options(_ITEMS_OPTION)
        stmt = stmt.order_by(ShipmentStage.shipment_id.desc(), ShipmentStage.stage_order)
        return [to_route(st, with_items) for st in self.session.scalars(stmt)]

    def list_all_routes(self, active_only: bool = False, with_items: bool = False) -> list[RouteDTO]:
        """Администратор: все пути."""
        return self._list_routes(active_only=active_only, with_items=with_items)

    def list_routes_for_warehouse(
        self, warehouse_id: int, active_only: bool = False, with_items: bool = False
    ) -> list[RouteDTO]:
        """Кладовщик: пути, которые уходят с его склада или приходят на него."""
        return self._list_routes(
            or_(
                ShipmentStage.from_warehouse_id == warehouse_id,
                ShipmentStage.to_warehouse_id == warehouse_id,
            ),
            active_only=active_only,
            with_items=with_items,
        )

    def list_routes_for_driver(
        self, driver_id: int, active_only: bool = True, with_items: bool = False
    ) -> list[RouteDTO]:
        """Водитель: его пути (по умолчанию только активные)."""
        return self._list_routes(
            ShipmentStage.driver_id == driver_id,
            active_only=active_only,
            with_items=with_items,
        )

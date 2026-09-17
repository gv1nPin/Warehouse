from collections.abc import Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from Warehouse.api.dto import NewStage, ShipmentDTO
from Warehouse.dal.entities import Shipment, ShipmentStage, StageItem
from Warehouse.api.mappers import to_shipment
from .base_repository import BaseRepository
from .shipment_stage_repository import ITEMS_OPTION, STAGE_OPTIONS


class ShipmentRepository(BaseRepository[Shipment]):
    """Отгрузки (Shipments) — «шапка» перевозки. Этапы и товары — в своих репозиториях."""

    model = Shipment

    def _select(self):
        return select(Shipment).options(
            joinedload(Shipment.status),
            joinedload(Shipment.creator),
            selectinload(Shipment.stages).options(*STAGE_OPTIONS, ITEMS_OPTION),
        )

    # ---------- Чтение ----------

    def get_by_id(self, shipment_id: int) -> ShipmentDTO | None:
        """Отгрузка целиком: все этапы и все товары."""
        sh = self._one(self._select().where(Shipment.id == shipment_id))
        return to_shipment(sh) if sh else None

    def get_status_id(self, shipment_id: int) -> int | None:
        """Быстрая проверка статуса без загрузки этапов."""
        return self.session.scalar(select(Shipment.status_id).where(Shipment.id == shipment_id))

    def list_by_creator(self, creator_id: int) -> list[ShipmentDTO]:
        stmt = self._select().where(Shipment.creator_id == creator_id).order_by(Shipment.id.desc())
        return [to_shipment(sh) for sh in self._all(stmt)]

    # ---------- Запись ----------

    def create(
        self,
        creator_id: int,
        planned_date: date,
        status_id: int,
        stages: Sequence[NewStage] = (),
        stage_status_id: int | None = None,
    ) -> int:
        """Создаёт отгрузку. Если переданы этапы — создаёт их (с товарами) и нумерует по порядку.

        stage_status_id — статус этапов; по умолчанию такой же, как у отгрузки.
        """
        shipment = Shipment(creator_id=creator_id, planned_date=planned_date, status_id=status_id)
        for order, stage in enumerate(stages, start=1):
            shipment.stages.append(
                ShipmentStage(
                    stage_order=order,
                    status_id=stage_status_id or status_id,
                    from_warehouse_id=stage.from_warehouse_id,
                    to_warehouse_id=stage.to_warehouse_id,
                    driver_id=stage.driver_id,
                    items=[
                        StageItem(product_id=i.product_id, document_quantity=i.quantity)
                        for i in stage.items
                    ],
                )
            )
        return self._add(shipment).id

    def set_status(self, shipment_id: int, status_id: int) -> bool:
        return self._update(shipment_id, status_id=status_id)

    def set_planned_date(self, shipment_id: int, planned_date: date) -> bool:
        return self._update(shipment_id, planned_date=planned_date)

    def delete(self, shipment_id: int) -> bool:
        """Полное удаление (этапы и товары удалятся каскадом). Только для черновиков."""
        return self._delete(shipment_id)

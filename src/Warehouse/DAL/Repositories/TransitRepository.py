from typing import Optional
from sqlalchemy import select, update
from src.Warehouse.DAL.Entities.models import Shipment, ShipmentStage, StageItem
from src.Warehouse.DAL.SQLAlchemyUnitOfWork import SQLAlchemyUnitOfWork

class TransitRepository:
    def __init__(self, uow: SQLAlchemyUnitOfWork):
        self.uow = uow

    def get_stage_by_id(self, stage_id: int) -> Optional[dict]:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if not stage:
            return None
        return {
            "id": stage.id,
            "shipment_id": stage.shipment_id,
            "stage_order": stage.stage_order,
            "status_id": stage.status_id,
            "from_warehouse_id": stage.from_warehouse_id
        }

    def update_shipment_status(self, shipment_id: int, status_id: int) -> None:
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        shipment = self.uow.session.scalars(stmt).first()
        if shipment:
            shipment.status_id = status_id

    def update_stage_status(self, stage_id: int, status_id: int) -> None:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if stage:
            stage.status_id = status_id

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        item = StageItem(
            stage_id=stage_id,
            product_id=product_id,
            document_quantity=document_quantity
        )
        self.uow.session.add(item)

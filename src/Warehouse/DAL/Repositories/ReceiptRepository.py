from datetime import datetime
from typing import List, Optional
from sqlalchemy import select
from Warehouse.DAL.Entities.Shipments import Shipment, ShipmentStage, StageItem
from Warehouse.DAL.UnitOfWork import UnitOfWork

class ReceiptRepository:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    def get_incoming_stages_by_warehouse(self, warehouse_id: int, status_id: int) -> List[dict]:
        stmt = select(ShipmentStage).where(
            ShipmentStage.to_warehouse_id == warehouse_id, 
            ShipmentStage.status_id == status_id
        )
        stages = self.uow.session.scalars(stmt).all()
        return [
            {
                "stage_id": s.id,
                "shipment_id": s.shipment_id,
                "stage_order": s.stage_order,
                "planned_date": s.sent_at.date() if s.sent_at else None,
                "sent_at": s.sent_at
            } for s in stages
        ]

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
            "to_warehouse_id": stage.to_warehouse_id
        }

    def update_item_actual_quantity(self, stage_id: int, product_id: int, actual_quantity: float) -> None:
        stmt = select(StageItem).where(StageItem.stage_id == stage_id, StageItem.product_id == product_id)
        item = self.uow.session.scalars(stmt).first()
        if not item:
            raise Exception(f"Товар {product_id} не связан с этапом {stage_id}.")
        item.actual_quantity = actual_quantity

    def get_stage_items(self, stage_id: int) -> List[dict]:
        stmt = select(StageItem).where(StageItem.stage_id == stage_id)
        items = self.uow.session.scalars(stmt).all()
        return [
            {
                "product_id": i.product_id,
                "document_quantity": i.document_quantity,
                "actual_quantity": i.actual_quantity
            } for i in items
        ]

    def complete_stage(self, stage_id: int, status_id: int, acceptor_id: int, received_at: datetime) -> None:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if stage:
            stage.status_id = status_id
            stage.acceptor_id = acceptor_id
            stage.received_at = received_at

    def get_stage_by_order(self, shipment_id: int, stage_order: int) -> Optional[dict]:
        stmt = select(ShipmentStage).where(
            ShipmentStage.shipment_id == shipment_id, 
            ShipmentStage.stage_order == stage_order
        )
        stage = self.uow.session.scalars(stmt).first()
        if not stage:
            return None
        return {"id": stage.id}

    def update_shipment_status(self, shipment_id: int, status_id: int) -> None:
        stmt = select(Shipment).where(Shipment.id == shipment_id)
        shipment = self.uow.session.scalars(stmt).first()
        if shipment:
            shipment.status_id = status_id

from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from Warehouse.DAL.Entities.Shipments import Shipment, ShipmentStage, StageItem, StockOnWarehouse
from Warehouse.DAL.SQLAlchemyUnitOfWork import SQLAlchemyUnitOfWork

class DispatchRepository:
    def __init__(self, uow: SQLAlchemyUnitOfWork):
        self.uow = uow

    def create_shipment(self, status_id: int, creator_id: int, planned_date: date) -> int:
        shipment = Shipment(status_id=status_id, creator_id=creator_id, planned_date=planned_date)
        self.uow.session.add(shipment)
        self.uow.session.flush()  # Получаем сгенерированный БД ID без завершения транзакции
        return shipment.id

    def create_stage(self, shipment_id: int, stage_order: int, from_warehouse_id: int, to_warehouse_id: int, status_id: int) -> None:
        stage = ShipmentStage(
            shipment_id=shipment_id,
            stage_order=stage_order,
            status_id=status_id,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id
        )
        self.uow.session.add(stage)

    def get_stage_by_id(self, stage_id: int) -> Optional[dict]:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if not stage:
            return None
        return {
            "id": stage.id,
            "status_id": stage.status_id,
            "from_warehouse_id": stage.from_warehouse_id
        }

    def get_balance_for_update(self, warehouse_id: int, product_id: int) -> Optional[StockOnWarehouse]:
        # ВАЖНО: Возвращаем сам ОБЪЕКТ МОДЕЛИ с блокировкой строки в БД. 
        # Указаны точные имена полей из ORM-модели: Warehouse_id и Product_id
        stmt = (
            select(StockOnWarehouse)
            .where(StockOnWarehouse.Warehouse_id == warehouse_id, StockOnWarehouse.Product_id == product_id)
            .with_for_update()
        )
        return self.uow.session.scalars(stmt).first()

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        item = StageItem(stage_id=stage_id, product_id=product_id, document_quantity=document_quantity)
        self.uow.session.add(item)

    def get_stage_items(self, stage_id: int) -> List[dict]:
        stmt = select(StageItem).where(StageItem.stage_id == stage_id)
        items = self.uow.session.scalars(stmt).all()
        return [{"product_id": i.product_id, "document_quantity": i.document_quantity} for i in items]

    def increase_reservation(self, warehouse_id: int, product_id: int, amount: float) -> None:
        # Используем метод get_balance_for_update для получения заблокированного объекта остатка
        stock = self.get_balance_for_update(warehouse_id, product_id)
        if not stock:
            raise Exception(f"Запись остатков для товара {product_id} на складе {warehouse_id} не найдена.")
        
        # Модифицируем объект напрямую. Сессия UOW зафиксирует изменения при коммите.
        stock.reserved_quantity = float(stock.reserved_quantity) + amount
        stock.last_updated = datetime.now(timezone.utc).date()

    def update_stage_status(self, stage_id: int, status_id: int) -> None:
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if stage:
            stage.status_id = status_id

    def mark_stage_as_shipped(self, stage_id: int, status_id: int, sent_at: datetime) -> None:
        # Убрали скрытый импорт BLL бизнес-логики. Статус теперь прокидывается сверху.
        stmt = select(ShipmentStage).where(ShipmentStage.id == stage_id)
        stage = self.uow.session.scalars(stmt).first()
        if stage:
            stage.status_id = status_id
            stage.sent_at = sent_at

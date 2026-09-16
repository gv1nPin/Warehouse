import logging
from datetime import date, datetime, timezone
from typing import List
from Warehouse.BLL.Interfaces.ShipmentService import AbstractShipmentDispatchService
from Warehouse.Common import ShipmentStatus
from Warehouse.API.Mappers.ShipmentsMappers import ShipmentMapper

class BusinessLogicException(Exception): pass
class InsufficientStockException(Exception): pass
class EntityNotFoundException(Exception): pass
class AccessDeniedException(Exception): pass

class ShipmentDispatchService(AbstractShipmentDispatchService):
    def __init__(self, uow):
        self.uow = uow

    def create_shipment_draft(self, creator_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        logging.info(f"Сотрудник ID {creator_id} инициировал создание черновика на дату {planned_date}")
        if planned_date  None:
        with self.uow:
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Указанный этап перевозки не найден.")
                
            if stage["status_id"] != ShipmentStatus.DRAFT:
                raise BusinessLogicException("Добавление товаров разрешено только в статусе 'Черновик'.")
            
            stock = self.uow.dispatch.get_balance_for_update(stage["from_warehouse_id"], product_id)
            quantity = float(stock.quantity) if stock else 0.0
            reserved_quantity = float(stock.reserved_quantity) if stock else 0.0
            
            if (quantity - reserved_quantity)  None:
        logging.info(f"Запуск резервирования остатков для этапа ID {stage_id}")
        with self.uow:  
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            items = self.uow.dispatch.get_stage_items(stage_id)
            if not items:
                raise BusinessLogicException("Невозможно зарезервировать пустой этап.")
                
            for item in items:
                self.uow.dispatch.increase_reservation(
                    warehouse_id=stage["from_warehouse_id"], 
                    product_id=item["product_id"], 
                    amount=float(item["document_quantity"])  
                )
                
            self.uow.dispatch.update_stage_status(stage_id, status_id=ShipmentStatus.RESERVED)
            
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=stage.get("creator_id", 0),
                operation_type="STAGE_ITEMS_RESERVED",
                entity_name="Stage",
                entity_id=stage_id,
                details={"warehouse_id": stage["from_warehouse_id"], "items_count": len(items)}
            )
            self.uow.history.log_operation(audit_data)
            
            logging.info(f" На Складе ID {stage['from_warehouse_id']} успешно заблокирован резерв под этап {stage_id}")

    def ship_stage(self, stage_id: int) -> None:
        with self.uow:  
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            if stage["status_id"] != ShipmentStatus.RESERVED:
                raise BusinessLogicException("Разрешено отправлять только зарезервированные этапы грузов.")
                
            self.uow.dispatch.mark_stage_as_shipped(
                stage_id=stage_id, 
                status_id=ShipmentStatus.SHIPPED, 
                sent_at=datetime.now(timezone.utc)
            )
            
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=stage.get("creator_id", 0),
                operation_type="STAGE_SHIPPED",
                entity_name="Stage",
                entity_id=stage_id,
                details={"from_warehouse_id": stage["from_warehouse_id"], "to_warehouse_id": stage["to_warehouse_id"]}
            )
            self.uow.history.log_operation(audit_data)
            
            logging.info(f" Транспорт выехал со склада отправления. Этап {stage_id} переведен в статус SHIPPED")

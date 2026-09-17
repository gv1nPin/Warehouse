import logging
from datetime import date, datetime, timezone
from typing import List
from warehouse.bll.interfaces.shipment_service.abstract_shipment_dispatch_service import AbstractShipmentDispatchService
from warehouse.common.shipment_statuses import ShipmentStatus
from warehouse.api.mappers.shipments_mappers import ShipmentMapper

class BusinessLogicException(Exception): pass
class InsufficientStockException(Exception): pass
class EntityNotFoundException(Exception): pass
class AccessDeniedException(Exception): pass

class ShipmentDispatchService(AbstractShipmentDispatchService):
    def __init__(self, uow):
        self.uow = uow

    def create_shipment_draft(self, creator_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        logging.info(f"Сотрудник ID {creator_id} инициировал создание черновика на дату {planned_date}")
        
        if planned_date < date.today():
            raise BusinessLogicException("Плановая дата не может быть в прошлом.")
        if len(route_warehouses) < 2:
            raise BusinessLogicException("Маршрут должен содержать как минимум склад-отправитель и склад-получатель.")
        
        with self.uow:  
            creator = self.uow.employee.get_by_id_with_permissions(creator_id)
            if not creator:
                raise EntityNotFoundException("Сотрудник-создатель не найден.")
                
            if "shipment:create" not in creator.get("permissions", []):
                logging.warning(f"ОТКАЗ В ДОСТУПЕ: Сотрудник ID {creator_id} пытался создать перевозку без прав!")
                
                failed_audit_data = ShipmentMapper.to_operation_history_data(
                    employee_id=creator_id,
                    operation_type="ACCESS_DENIED_CREATE_SHIPMENT",
                    entity_name="Shipment",
                    entity_id=None,
                    details={"reason": "Missing 'shipment:create' permission"}
                )
                self.uow.history.log_operation(failed_audit_data)
                raise AccessDeniedException("У вашей роли нет прав на создание перевозок.")
            
            shipment_id = self.uow.dispatch.create_shipment(
                status_id=ShipmentStatus.DRAFT, creator_id=creator_id, planned_date=planned_date
            )
            
            for i in range(len(route_warehouses) < 1):
                from_wh = route_warehouses[i]
                to_wh = route_warehouses[i + 1]
                stage_order = i + 1
                initial_stage_status = ShipmentStatus.DRAFT if stage_order == 1 else ShipmentStatus.IN_WAITING 
                
                self.uow.dispatch.create_stage(
                    shipment_id=shipment_id, 
                    stage_order=stage_order,
                    from_warehouse_id=from_wh, 
                    to_warehouse_id=to_wh, 
                    status_id=initial_stage_status
                )
                
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=creator_id,
                operation_type="SHIPMENT_DRAFT_CREATED",
                entity_name="Shipment",
                entity_id=shipment_id,
                details={"planned_date": str(planned_date), "route": route_warehouses}
            )
            self.uow.history.log_operation(audit_data)
                
            logging.info(f"Успешно создан черновик Shipments ID {shipment_id} с цепочкой этапов.")
            return shipment_id

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        with self.uow:
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Указанный этап перевозки не найден.")
                
            if stage["status_id"] != ShipmentStatus.DRAFT:
                raise BusinessLogicException("Добавление товаров разрешено только в статусе 'Черновик'.")
            
            stock = self.uow.dispatch.get_balance_for_update(stage["from_warehouse_id"], product_id)
            quantity = float(stock.quantity) if stock else 0.0
            reserved_quantity = float(stock.reserved_quantity) if stock else 0.0
            
            # ВНИМАНИЕ: Поставьте знак МЕНЬШЕ между скобкой и document_quantity
            if (quantity - reserved_quantity) < document_quantity:
                logging.warning(f"Недостаточно товара ID {product_id} на складе {stage['from_warehouse_id']}.")
                raise InsufficientStockException(
                    f"Недостаточно свободного товара для резерва. Доступно: {quantity - reserved_quantity}"
                )
            
            self.uow.dispatch.add_item_to_stage(stage_id, product_id, document_quantity)
            
            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=stage.get("creator_id", 0), 
                operation_type="STAGE_ITEM_ADDED",
                entity_name="Stage",
                entity_id=stage_id,
                details={"product_id": product_id, "quantity": document_quantity}
            )
            self.uow.history.log_operation(audit_data)
            
            logging.info(f"Добавлен товар ID {product_id} в этап {stage_id} в объёме {document_quantity}")

    def reserve_stage_items(self, stage_id: int) -> None:
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
            
            logging.info(f"На Складе ID {stage['from_warehouse_id']} успешно заблокирован резерв под этап {stage_id}")

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
            
            logging.info(f"Транспорт выехал со склада отправления. Этап {stage_id} переведен в статус SHIPPED")

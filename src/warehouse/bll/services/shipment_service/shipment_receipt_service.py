import logging
from datetime import datetime, timezone 
from typing import List
from warehouse.common import ShipmentStatus
from warehouse.api.mappers.shipments_mappers import ShipmentMapper
from warehouse.bll.interfaces.shipment_service.abstract_shipment_receipt_service import AbstractShipmentReceiptService
from warehouse.bll.interfaces.shipment_service.abstract_shipment_transit_coordinator import AbstractShipmentTransitCoordinator 

class BusinessLogicException(Exception): pass
class AccessDeniedException(Exception): pass
class EntityNotFoundException(Exception): pass

class ShipmentReceiptService(AbstractShipmentReceiptService):
    def __init__(self, uow, transit_coordinator: AbstractShipmentTransitCoordinator):
        self.uow = uow
        self.transit_coordinator = transit_coordinator

    def get_incoming_stages(self, warehouse_id: int) -> List[dict]:
        return self.uow.receipt.get_incoming_stages_by_warehouse(warehouse_id, status_id=ShipmentStatus.SHIPPED)

    def enter_actual_quantity(self, stage_id: int, product_id: int, actual_quantity: float) -> None:
        if actual_quantity < 0:
            raise BusinessLogicException("Фактическое количество не может быть отрицательным.")
            
        with self.uow:  
            stage = self.uow.receipt.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
            if stage["status_id"] != ShipmentStatus.SHIPPED:
                raise BusinessLogicException("Вносить фактическое количество можно только для грузов в пути.")
                
            self.uow.receipt.update_item_actual_quantity(stage_id, product_id, actual_quantity)
            logging.info(f"Кладовщик внес факт по товару ID {product_id} для этапа {stage_id}: {actual_quantity}")

    def accept_stage(self, stage_id: int, employee_id: int) -> None:
        logging.info(f"Сотрудник ID {employee_id} закрывает приёмку для этапа ID {stage_id}")
        with self.uow:  
            stage = self.uow.receipt.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            employee = self.uow.employee.get_by_id_with_permissions(employee_id)
            if not employee:
                raise EntityNotFoundException("Сотрудник приёмки не найден.")
                
            if "shipment:accept" not in employee.get("permissions", []):
                logging.warning(f" ОТКАЗ В ДОСТУПЕ: Попытка приемки этапа {stage_id} сотрудником ID {employee_id} без прав.")
                raise AccessDeniedException("У вашей роли нет прав на приемку грузов.")
                
            if employee["warehouse_id"] != stage["to_warehouse_id"]:
                logging.warning(f" Нарушение периметра: Кладовщик склада...")
                
                failed_wh_audit = ShipmentMapper.to_operation_history_data(
                    employee_id=employee_id,
                    operation_type="SECURITY_PERIMETER_VIOLATION",
                    entity_name="Stage",
                    entity_id=stage_id,
                    details={"employee_warehouse": employee["warehouse_id"], "target_warehouse": stage["to_warehouse_id"]}
                )
                self.uow.history.log_operation(failed_wh_audit)
                raise AccessDeniedException("Вы не можете принять груз, направленный на чужной склад.")
            
            stage_items = self.uow.receipt.get_stage_items(stage_id)
            for item in stage_items:
                if item["actual_quantity"] is None:
                    raise BusinessLogicException(f"Заполните фактическое количество для товара ID {item['product_id']}.")
            
            has_discrepancies = any(float(item["actual_quantity"]) != float(item["document_quantity"]) for item in stage_items)
            final_status = ShipmentStatus.DISCREPANCY if has_discrepancies else ShipmentStatus.RECEIVED
            
            self.uow.receipt.complete_stage(
                stage_id=stage_id, 
                status_id=final_status, 
                acceptor_id=employee_id, 
                received_at=datetime.now(timezone.utc)
            )
            logging.info(f"Этап {stage_id} успешно завершен со статусом: {final_status.name}")

            audit_data = ShipmentMapper.to_operation_history_data(
                employee_id=employee_id,
                operation_type="STAGE_ACCEPTED_RECEIVED" if final_status == ShipmentStatus.RECEIVED else "STAGE_ACCEPTED_WITH_DISCREPANCY",
                entity_name="Stage",
                entity_id=stage_id,
                details={"warehouse_id": employee["warehouse_id"]}
            )
            self.uow.history.log_operation(audit_data)

            next_stage = self.uow.receipt.get_stage_by_order(
                shipment_id=stage["shipment_id"], 
                stage_order=stage["stage_order"] + 1
            )
            
            if next_stage:
                logging.info(f"Передаем управление кросс-докингу для переброски на этап ID {next_stage['id']}")
                accepted_items = {item["product_id"]: float(item["actual_quantity"]) for item in stage_items}
                self.transit_coordinator.move_to_next_stage(stage_id, next_stage["id"], accepted_items)
            else:
                self.uow.receipt.update_shipment_status(stage["shipment_id"], status_id=final_status)
                logging.info(f" Поставка {stage['shipment_id']} полностью завершила свой маршрут.")

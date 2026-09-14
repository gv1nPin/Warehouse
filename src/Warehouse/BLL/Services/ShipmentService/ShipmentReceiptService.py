from datetime import datetime, timezone 
from typing import List
from Warehouse.BLL.Common import ShipmentStatus
from Warehouse.BLL.Interfaces.ShipmentService import (
    AbstractShipmentReceiptService, 
    AbstractShipmentTransitCoordinator
)

class BusinessLogicException(Exception): pass
class AccessDeniedException(Exception): pass
class EntityNotFoundException(Exception): pass

class ShipmentReceiptService(AbstractShipmentReceiptService):
    def __init__(self, uow, transit_coordinator: AbstractShipmentTransitCoordinator):
        """Инициализирует сервис управления приёмкой грузов.

        Args:
            uow: Универсальный Unit of Work (дает доступ к репозиториям и сессии).
            transit_coordinator (AbstractShipmentTransitCoordinator): Зависимость от координатора транзита.
        """
        self.uow = uow
        self.transit_coordinator = transit_coordinator

    def get_incoming_stages(self, warehouse_id: int) -> List[dict]:
        # Чтение выполняется вне транзакции, берем репозиторий через сессию по умолчанию или открываем транзакцию
        with self.uow:
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

    def accept_stage(self, stage_id: int, employee_id: int) -> None:
        with self.uow:  
            stage = self.uow.receipt.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            # Запрашиваем сотрудника через свойство uow.employee
            employee = self.uow.employee.get_by_id_with_permissions(employee_id)
            if not employee:
                raise EntityNotFoundException("Сотрудник приёмки не найден.")
                
            if "shipment:accept" not in employee.get("permissions", []):
                raise AccessDeniedException("У вашей роли нет прав на приемку грузов.")
                
            if employee["warehouse_id"] != stage["to_warehouse_id"]:
                raise AccessDeniedException("Вы не можете принять груз, направленный на чужой склад.")
            
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

            next_stage = self.uow.receipt.get_stage_by_order(
                shipment_id=stage["shipment_id"], 
                stage_order=stage["stage_order"] + 1
            )
            
            if next_stage:
                accepted_items = {item["product_id"]: float(item["actual_quantity"]) for item in stage_items}
                # Передаем управление координатору транзита в рамках ТЕКУЩЕЙ транзакции UOW
                self.transit_coordinator.move_to_next_stage(stage_id, next_stage["id"], accepted_items)
            else:
                final_shipment_status = ShipmentStatus.DISCREPANCY if has_discrepancies else ShipmentStatus.RECEIVED
                self.uow.receipt.update_shipment_status(stage["shipment_id"], status_id=final_shipment_status)

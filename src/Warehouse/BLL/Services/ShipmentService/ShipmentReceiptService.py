from datetime import datetime
from typing import List
from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Interfaces.ShipmentService import (
    AbstractShipmentReceiptService, 
    AbstractShipmentTransitCoordinator
)

class BusinessLogicException(Exception): pass
class AccessDeniedException(Exception): pass
class EntityNotFoundException(Exception): pass

class ShipmentReceiptService(AbstractShipmentReceiptService):
    def __init__(self, shipment_repo, employee_repo, transit_coordinator: AbstractShipmentTransitCoordinator):
        """Инициализирует сервис управления приёмкой грузов.

        Args:
            shipment_repo: Репозиторий из слоя DAL для работы с перевозками и этапами.
            employee_repo: Репозиторий из слоя DAL для работы с сотрудниками.
            transit_coordinator (AbstractShipmentTransitCoordinator): Абстрактная зависимость 
                                                                     координатора транзита.
        """
        self.shipment_repo = shipment_repo
        self.employee_repo = employee_repo
        self.transit_coordinator = transit_coordinator  # Зависимость от абстрактного координатора

    def get_incoming_stages(self, warehouse_id: int) -> List[dict]:
        """Возвращает список всех этапов перевозок, которые сейчас находятся в пути к указанному складу.

        Args:
            warehouse_id (int): Идентификатор целевого склада (Warehouses).

        Returns:
            List[dict]: Список словарей с данными о прибывающих машинах (ID этапа, дата, отправитель и др.).
        """
        return self.shipment_repo.get_incoming_stages_by_warehouse(warehouse_id, status_id=ShipmentStatus.SHIPPED)

    def enter_actual_quantity(self, stage_id: int, product_id: int, actual_quantity: float) -> None:
        """Записывает фактически пересчитанное кладовщиком количество товара для строки этапа.

        Args:
            stage_id (int): Идентификатор текущего этапа перевозки (ShipmentStages).
            product_id (int): Идентификатор проверяемого товара (Products).
            actual_quantity (float): Фактически обнаруженное физическое количество товара.

        Raises:
            BusinessLogicException: Если количество отрицательное или этап находится не в статусе 'Отправлено'.
        """
        if actual_quantity < 0:
            raise BusinessLogicException("Фактическое количество не может быть отрицательным.")
            
        stage = self.shipment_repo.get_stage_by_id(stage_id)
        if stage["status_id"] != ShipmentStatus.SHIPPED:
            raise BusinessLogicException("Вносить фактическое количество можно только для грузов в пути.")
            
        self.shipment_repo.update_item_actual_quantity(stage_id, product_id, actual_quantity)

    def accept_stage(self, stage_id: int, employee_id: int) -> None:
        """Финально закрывает этап приёмки груза на складе, проверяет расхождения 
        и запускает автоматический транзит к следующему узлу, если маршрут не окончен.

        Args:
            stage_id (int): Идентификатор закрываемого этапа (ShipmentStages).
            employee_id (int): Идентификатор принимающего сотрудника (Employees).

        Raises:
            EntityNotFoundException: Если этап или сотрудник приёмки не найдены в системе.
            AccessDeniedException: Если склад сотрудника не совпадает со складом назначения этапа.
            BusinessLogicException: Если у товаров остались незаполненные поля фактического количества (NULL).
        """
        stage = self.shipment_repo.get_stage_by_id(stage_id)
        if not stage:
            raise EntityNotFoundException("Этап не найден.")
            
        employee = self.employee_repo.get_by_id(employee_id)
        if not employee:
            raise EntityNotFoundException("Сотрудник приёмки не найден.")
        if employee["warehouse_id"] != stage["to_warehouse_id"]:
            raise AccessDeniedException("Вы не можете принять груз, направленный на чужой склад.")
        
        stage_items = self.shipment_repo.get_stage_items(stage_id)
        for item in stage_items:
            if item["actual_quantity"] is None:
                raise BusinessLogicException(f"Заполните фактическое количество для товара ID {item['product_id']}.")
        
        has_discrepancies = any(item["actual_quantity"] != item["document_quantity"] for item in stage_items)
        final_status = ShipmentStatus.DISCREPANCY if has_discrepancies else ShipmentStatus.RECEIVED
        
        self.shipment_repo.complete_stage(
            stage_id=stage_id, 
            status_id=final_status, 
            acceptor_id=employee_id, 
            received_at=datetime.now()
        )

        next_stage = self.shipment_repo.get_stage_by_order(
            shipment_id=stage["shipment_id"], 
            stage_order=stage["stage_order"] + 1
        )
        
        if next_stage:
            accepted_items = {item["product_id"]: float(item["actual_quantity"]) for item in stage_items}
            self.transit_coordinator.move_to_next_stage(stage_id, next_stage["id"], accepted_items)
        else:
            final_shipment_status = ShipmentStatus.DISCREPANCY if has_discrepancies else ShipmentStatus.RECEIVED
            self.shipment_repo.update_shipment_status(stage["shipment_id"], status_id=final_shipment_status)

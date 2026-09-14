# src/Warehouse/BLL/Services/ShipmentService/ShipmentDispatchService.py
from datetime import date, datetime, timezone
from typing import List
from src.Warehouse.BLL.Interfaces.ShipmentService import AbstractShipmentDispatchService
from src.Warehouse.BLL.Common import ShipmentStatus

class BusinessLogicException(Exception): pass
class InsufficientStockException(Exception): pass
class EntityNotFoundException(Exception): pass
class AccessDeniedException(Exception): pass

class ShipmentDispatchService(AbstractShipmentDispatchService):
    def __init__(self, uow):
        """Инициализирует сервис управления отправкой грузов."""
        self.uow = uow

    def create_shipment_draft(self, creator_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        if planned_date < date.today():
            raise BusinessLogicException("Плановая дата не может быть в прошлом.")
        if len(route_warehouses) < 2:
            raise BusinessLogicException("Маршрут должен содержать как минимум склад-отправитель и склад-получатель.")
        
        with self.uow:  
            # Вызовы переведены на свойства uow
            creator = self.uow.employee.get_by_id_with_permissions(creator_id)
            if not creator:
                raise EntityNotFoundException("Сотрудник-создатель не найден.")
                
            if "shipment:create" not in creator.get("permissions", []):
                raise AccessDeniedException("У вашей роли нет прав на создание перевозок.")
            
            shipment_id = self.uow.dispatch.create_shipment(
                status_id=ShipmentStatus.DRAFT, 
                creator_id=creator_id, 
                planned_date=planned_date
            )
            
            for i in range(len(route_warehouses) - 1):
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
                
            return shipment_id

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        if document_quantity <= 0:
            raise BusinessLogicException("Количество должно быть больше нуля.")
        
        with self.uow:
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Указанный этап перевозки не найден.")
                
            if stage["status_id"] != ShipmentStatus.DRAFT:
                raise BusinessLogicException("Добавление товаров разрешено только в статусе 'Черновик'.")
            
            # Из репозитория возвращается живой SQLAlchemy-объект
            stock = self.uow.dispatch.get_balance_for_update(stage["from_warehouse_id"], product_id)
            quantity = float(stock.quantity) if stock else 0.0
            reserved_quantity = float(stock.reserved_quantity) if stock else 0.0
            
            if (quantity - reserved_quantity) < document_quantity:
                raise InsufficientStockException(
                    f"Недостаточно свободного товара для резерва. Доступно: {quantity - reserved_quantity}"
                )
            
            self.uow.dispatch.add_item_to_stage(stage_id, product_id, document_quantity)

    def reserve_stage_items(self, stage_id: int) -> None:
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

    def ship_stage(self, stage_id: int) -> None:
        with self.uow:  
            stage = self.uow.dispatch.get_stage_by_id(stage_id)
            if not stage:
                raise EntityNotFoundException("Этап не найден.")
                
            if stage["status_id"] != ShipmentStatus.RESERVED:
                raise BusinessLogicException("Разрешено отправлять только зарезервированные этапы грузов.")
                
            # Исправлено: Прокидываем status_id=ShipmentStatus.SHIPPED согласно сигнатуре репозитория
            self.uow.dispatch.mark_stage_as_shipped(
                stage_id=stage_id, 
                status_id=ShipmentStatus.SHIPPED, 
                sent_at=datetime.now(timezone.utc)
            )

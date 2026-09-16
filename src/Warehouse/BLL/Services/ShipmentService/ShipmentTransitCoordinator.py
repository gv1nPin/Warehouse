import logging
from typing import Dict
from Warehouse.Common import ShipmentStatus
from Warehouse.BLL.Interfaces.ShipmentService import (
    AbstractShipmentTransitCoordinator, 
    AbstractShipmentDispatchService
)

class BusinessLogicException(Exception): pass
class EntityNotFoundException(BusinessLogicException): pass 

class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    def __init__(self, uow, dispatch_service: AbstractShipmentDispatchService):
        self.uow = uow
        self.dispatch_service = dispatch_service

    def move_to_next_stage(self, current_stage_id: int, next_stage_id: int, accepted_items: Dict[int, float]) -> None:
        logging.info(f" Инициализация кросс-докинга: этап {current_stage_id} -> этап {next_stage_id}")
        with self.uow:  
            next_stage = self.uow.transit.get_stage_by_id(next_stage_id)
            if not next_stage:
                raise EntityNotFoundException("Следующий этап транзита не найден.")
            
            self.uow.transit.update_shipment_status(next_stage["shipment_id"], status_id=ShipmentStatus.IN_TRANSIT_WH)
            
            has_items_to_forward = False
            for product_id, actual_qty in accepted_items.items():
                if actual_qty > 0:
                    self.uow.transit.add_item_to_stage(
                        stage_id=next_stage_id, 
                        product_id=product_id, 
                        document_quantity=actual_qty
                    )
                    has_items_to_forward = True
            
            self.uow.transit.update_stage_status(next_stage_id, status_id=ShipmentStatus.DRAFT)
            
            if has_items_to_forward:
                logging.info(f"Автоматическое перерезервирование товаров для следующего плеча поставки...")
                self.dispatch_service.reserve_stage_items(next_stage_id)

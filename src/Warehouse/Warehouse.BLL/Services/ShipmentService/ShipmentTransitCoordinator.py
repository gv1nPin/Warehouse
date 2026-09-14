from typing import Dict
from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Interfaces.ShipmentService import (
    AbstractShipmentTransitCoordinator, 
    AbstractShipmentDispatchService
)

class EntityNotFoundException(Exception): pass

class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    def __init__(self, uow, shipment_repo, dispatch_service: AbstractShipmentDispatchService):
        """Инициализирует координатор транзита и кросс-докинга.

        Args:
            uow: Unit of Work для разделения транзакции с вызывающим сервисом.
            shipment_repo: Репозиторий из слоя DAL для управления поставками и этапами в БД.
            dispatch_service (AbstractShipmentDispatchService): Абстрактная зависимость сервиса отправки 
                                                               для автоматического резервирования.
        """
        self.uow = uow
        self.shipment_repo = shipment_repo
        self.dispatch_service = dispatch_service   # Зависимость от абстрактного сервиса отправки

    def move_to_next_stage(self, current_stage_id: int, next_stage_id: int, accepted_items: Dict[int, float]) -> None:
        """Обеспечивает автоматический перевод груза на следующее плечо доставки при кросс-докинге.
        
        Метод считывает фактически доехавшие товары, переносит их как плановое количество (document_quantity) 
        для следующего этапа маршрута, активирует статус черновика для новой отправки и мгновенно блокирует 
        весь прибывший объём в резерве транзитного склада, защищая его от нецелевого списания.

        Args:
            current_stage_id (int): Идентификатор только что успешно принятого этапа перевозки.
            next_stage_id (int): Идентификатор следующего по цепочке этапа, который нужно подготовить.
            accepted_items (Dict[int, float]): Словарь принятых позиций, где ключ — product_id (int), 
                                               а значение — actual_quantity (float).
        """
        with self.uow:  
            next_stage = self.shipment_repo.get_stage_by_id(next_stage_id)
            if not next_stage:
                raise EntityNotFoundException("Следующий этап транзита не найден.")
            
            self.shipment_repo.update_shipment_status(next_stage["shipment_id"], status_id=ShipmentStatus.IN_TRANSIT_WH)
            
            has_items_to_forward = False
            
            for product_id, actual_qty in accepted_items.items():
                if actual_qty > 0:
                    self.shipment_repo.add_item_to_stage(
                        stage_id=next_stage_id, 
                        product_id=product_id, 
                        document_quantity=actual_qty
                    )
                    has_items_to_forward = True
            
            self.shipment_repo.update_stage_status(next_stage_id, status_id=ShipmentStatus.DRAFT)
            
            if has_items_to_forward:
                # Перевызываем сервис отправки. Так как сессия UOW общая, всё запишется вместе
                self.dispatch_service.reserve_stage_items(next_stage_id)

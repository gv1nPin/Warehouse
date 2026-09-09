from typing import Dict
from src.Warehouse.BLL.Common import ShipmentStatus
from src.Warehouse.BLL.Interfaces.ShipmentService import (
    AbstractShipmentTransitCoordinator, 
    AbstractShipmentDispatchService
)

class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    def __init__(self, shipment_repo, dispatch_service: AbstractShipmentDispatchService):
        """Инициализирует координатор транзита и кросс-докинга.

        Args:
            shipment_repo: Репозиторий из слоя DAL для управления поставками и этапами в БД.
            dispatch_service (AbstractShipmentDispatchService): Абстрактная зависимость сервиса отправки 
                                                               для автоматического резервирования.
        """
        self.shipment_repo = shipment_repo
        self.dispatch_service = dispatch_service  # Зависимость от абстрактного сервиса отправки

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
        # Получаем информацию о следующем этапе маршрута из базы данных
        next_stage = self.shipment_repo.get_stage_by_id(next_stage_id)
        
        # 1. Меняем статус всей родительской перевозки (Shipments) на 'На транзитном складе' (status_id = 7)
        self.shipment_repo.update_shipment_status(next_stage["shipment_id"], status_id=ShipmentStatus.IN_TRANSIT_WH)
        
        has_items_to_forward = False
        
        # 2. Переносим только реально доехавший товар на следующее плечо доставки
        for product_id, actual_qty in accepted_items.items():
            if actual_qty > 0:
                self.shipment_repo.add_item_to_stage(
                    stage_id=next_stage_id, 
                    product_id=product_id, 
                    document_quantity=actual_qty
                )
                has_items_to_forward = True
        
        # Переводим следующий этап из спящего режима (status_id = 5 'Ожидание') в 'Черновик' (status_id = 1)
        self.shipment_repo.update_stage_status(next_stage_id, status_id=ShipmentStatus.DRAFT)
        
        # 3. Автоматически бронируем прибывший груз под дальнейший путь, вызывая DispatchService
        if has_items_to_forward:
            self.dispatch_service.reserve_stage_items(next_stage_id)

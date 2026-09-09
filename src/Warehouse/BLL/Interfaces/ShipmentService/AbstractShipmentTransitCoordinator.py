from abc import ABC, abstractmethod
from typing import Dict

class AbstractShipmentTransitCoordinator(ABC):
    @abstractmethod
    def move_to_next_stage(self, current_stage_id: int, next_stage_id: int, accepted_items: Dict[int, float]) -> None:
        """Обеспечивает автоматический кросс-докинг на транзитном узле. 
        Метод берет фактически принятые товары текущего этапа, переносит их в качестве 
        планового документального количества (document_quantity) для следующего плеча маршрута 
        и мгновенно блокирует этот объём в резерве транзитного склада, защищая груз от списания 
        на другие нужды.

        Args:
            current_stage_id (int): Идентификатор только что завершенного этапа приёмки.
            next_stage_id (int): Идентификатор следующего по цепочке этапа перевозки, 
                                 который необходимо инициализировать.
            accepted_items (Dict[int, float]): Словарь фактически принятых товаров на текущем узле, 
                                               где ключ — product_id (int), 
                                               а значение — actual_quantity (float).
        
        Raises:
            BusinessLogicException: Если при автоматическом перерезервировании на транзитном складе 
                                    произошел сбой или нарушена целостность цепочки этапов.
        """
        pass

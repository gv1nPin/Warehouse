from abc import ABC, abstractmethod
from datetime import date
from typing import List

class AbstractShipmentDispatchService(ABC):
    @abstractmethod
    def create_shipment_draft(self, creator_id: int, planned_date: date, route_warehouses: List[int]) -> int:
        """Создает шапку Shipments и автоматически генерирует всю цепочку последовательных 
        этапов ShipmentStages на основе переданного маршрута складов.

        Args:
            creator_id (int): Идентификатор сотрудника (кладовщика-отправителя), создавшего заявку.
            planned_date (date): Плановая дата отправки груза из начальной точки маршрута.
            route_warehouses (List[int]): Массив ID складов, упорядоченный по ходу движения 
                                         (например: [Склад_А, Транзит_1, Склад_Б]).

        Returns:
            int: Идентификатор (ID) созданной перевозки из таблицы Shipments.
        """
        pass

    @abstractmethod
    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        """Добавляет товар в StageItems для указанного этапа. Перед добавлением 
        обязательно валидирует наличие свободного остатка (quantity - reserved_quantity) 
        на складе отправления этого этапа.

        Args:
            stage_id (int): Идентификатор этапа перевозки (ShipmentStages), в который добавляется товар.
            product_id (int): Идентификатор добавляемого товара (Products).
            document_quantity (float): Плановое количество товара для отправки по документам.
        """
        pass

    @abstractmethod
    def reserve_stage_items(self, stage_id: int) -> None:
        """Блокирует плановое количество товаров на складе отправления текущего этапа, 
        переводя его из свободного остатка в резерв (увеличивает reserved_quantity в StockOnWarehouse).
        Переводит статус этапа в состояние 'Зарезервировано'.

        Args:
            stage_id (int): Идентификатор этапа перевозки, товары которого необходимо зарезервировать.
        """
        pass

    @abstractmethod
    def ship_stage(self, stage_id: int) -> None:
        """Фиксирует факт физического выезда транспорта со склада отправления текущего этапа. 
        Устанавливает статус этапа в состояние 'Отправлено' и фиксирует время отправления (sent_at).
        Активирует триггер БД, который окончательно списывает товар с общего баланса и резерва склада.

        Args:
            stage_id (int): Идентификатор отправляемого этапа перевозки.
        """
        pass

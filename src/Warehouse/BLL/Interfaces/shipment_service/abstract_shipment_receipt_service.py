from abc import ABC, abstractmethod
from typing import List

class AbstractShipmentReceiptService(ABC):
    @abstractmethod
    def get_incoming_stages(self, warehouse_id: int) -> List[dict]:
        """Возвращает список всех этапов перевозок, которые физически находятся в пути 
        (status_id = 'Отправлено') и направляются на указанный склад.

        Args:
            warehouse_id (int): Идентификатор склада (Warehouses), на котором кладовщик 
                                ожидает прибытие груза.

        Returns:
            List[dict]: Список словарей, каждый из которых содержит информацию о прибывающем этапе:
                        [
                            {
                                "stage_id": int,
                                "shipment_id": int,
                                "stage_order": int,
                                "from_warehouse_title": str,
                                "planned_date": date,
                                "sent_at": datetime
                            },
                            ...
                        ]
        """
        pass

    @abstractmethod
    def enter_actual_quantity(self, stage_id: int, product_id: int, actual_quantity: float) -> None:
        """Записывает фактически пересчитанное кладовщиком количество товара для конкретной 
        строки текущего этапа перевозки в таблицу StageItems.

        Args:
            stage_id (int): Идентификатор принимаемого этапа перевозки (ShipmentStages).
            product_id (int): Идентификатор пересчитанного товара (Products).
            actual_quantity (float): Фактическое количество товара, обнаруженное при приёмке. 
                                     Должно быть строго не меньше нуля.
        
        Raises:
            BusinessLogicException: Если количество отрицательное или этап находится в неверном статусе.
        """
        pass

    @abstractmethod
    def accept_stage(self, stage_id: int, employee_id: int) -> None:
        """Финально фиксирует завершение приёмки этапа. 
        Метод проверяет права сотрудника, контролирует отсутствие незаполненных (NULL) позиций, 
        автоматически выставляет этапу статус («Принято» или «Принято с расхождениями») и 
        запускает координатора транзита, если этот склад промежуточный.

        Args:
            stage_id (int): Идентификатор закрываемого этапа перевозки.
            employee_id (int): Идентификатор принимающего сотрудника (кладовщика-получателя) 
                               для фиксации в поле acceptor_id.

        Raises:
            AccessDeniedException: Если склад сотрудника не совпадает со складом назначения этапа.
            BusinessLogicException: Если не все позиции груза были пересчитаны (остались NULL) 
                                    или этап уже был принят ранее.
        """
        pass

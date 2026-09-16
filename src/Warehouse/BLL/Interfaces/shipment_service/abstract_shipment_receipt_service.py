from abc import ABC, abstractmethod
from typing import List, Optional
from warehouse.api.dto import StageDTO, DiscrepancyDTO


class AbstractShipmentReceiptService(ABC):
    """Абстрактный интерфейс (контракт) для сервиса приемки поставок на складе."""

    @abstractmethod
    def get_incoming(self, employee_id: int) -> List[StageDTO]:
        """Получить список этапов поставок в статусе 'Отправлено', едущих на склад сотрудника.

        :param employee_id: Идентификатор сотрудника склада.
        :return: Список объектов StageDTO.
        :raises EntityNotFoundException: Если сотрудник не найден в системе.
        """
        pass

    @abstractmethod
    def enter_actual_quantity(
        self, 
        employee_id: int, 
        item_id: int, 
        quantity: float, 
        comment: Optional[str] = None
    ) -> None:
        """Внести фактическое количество поступившего товара по конкретной позиции этапа.

        :param employee_id: Идентификатор сотрудника, выполняющего операцию.
        :param item_id: Идентификатор позиции товара на этапе (StageItem).
        :param quantity: Фактически принятое количество товара (>= 0).
        :param comment: Обязательный комментарий при наличии расхождений.
        :raises BusinessLogicException: Если количество отрицательное или отсутствует 
                                        обязательный комментарий при расхождениях.
        :raises EntityNotFoundException: Если позиция или этап не найдены.
        :raises AccessDeniedException: Если груз принадлежит чужому периметру склада.
        """
        pass

    @abstractmethod
    def check_discrepancies(self, employee_id: int, stage_id: int) -> List[DiscrepancyDTO]:
        """Проверить и вернуть список позиций с расхождениями или незаполненным фактом.
        
        Данный метод не изменяет состояние данных в базе.

        :param employee_id: Идентификатор сотрудника.
        :param stage_id: Идентификатор проверяемого этапа поставки.
        :return: Список DTO с информацией о расхождениях (DiscrepancyDTO).
        :raises EntityNotFoundException: Если этап поставки не найден.
        """
        pass

    @abstractmethod
    def accept_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Окончательно принять этап поставки на склад с оприходованием остатков.

        Завершает этап, проставляет информацию о приемщике и времени, увеличивает 
        доступные остатки товаров на складе и передает управление транзитному координатору.

        :param employee_id: Идентификатор сотрудника, завершающего приемку.
        :param stage_id: Идентификатор принимаемого этапа.
        :return: Обновленный объект StageDTO с актуальным статусом приемки.
        :raises BusinessLogicException: Если этап не в статусе 'Отправлено' или 
                                        не по всем позициям заполнен факт.
        :raises EntityNotFoundException: Если этап или сотрудник не найдены.
        :raises AccessDeniedException: Если у сотрудника нет права 'shipment:accept' 
                                       или склад сотрудника не совпадает со складом назначения.
        """
        pass

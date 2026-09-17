from abc import ABC, abstractmethod
from datetime import date
from typing import List


class AbstractShipmentDispatchService(ABC):
    """Абстрактный интерфейс для сервиса отправки и диспетчеризации перевозок."""

    @abstractmethod
    def create_shipment_draft(
        self, employee_id: int, planned_date: date, route_warehouses: List[int]
    ) -> int:
        """Создает черновик перевозки и цепочку этапов на основе маршрута.

        ТЗ: Первый склад в route_warehouses должен совпадать со складом сотрудника.
        """
        pass

    @abstractmethod
    def add_item_to_stage(
        self, employee_id: int, stage_id: int, product_id: int, document_quantity: float
    ) -> None:
        """Добавляет товарную позицию на конкретный этап перевозки.

        ТЗ: Только в черновик и только на склад текущего сотрудника.
        """
        pass

    @abstractmethod
    def reserve_stage_items(self, employee_id: int, stage_id: int) -> None:
        """Блокирует и переводит доступный остаток товара в резерв под будущую отгрузку."""
        pass

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> None:
        """Выполняет фактическую отправку этапа груза со склада.

        ТЗ: Списывает остатки (quantity) со склада в зависимости от статуса (DRAFT/RESERVED).
        """
        pass

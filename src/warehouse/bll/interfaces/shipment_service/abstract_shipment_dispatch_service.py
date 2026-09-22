from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from warehouse.api.dto import (
    EmployeeDTO,
    NewStageItem,
    ShipmentDTO,
    StageDTO,
    StockItemDTO,
    WarehouseDTO,
)


class AbstractShipmentDispatchService(ABC):
    """Отправка груза: черновик перевозки, товары, резерв, отправка.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        shipment = dispatch.create_draft(employee_id, date(2026, 10, 1), [1, 2, 3])
        dispatch.add_item(employee_id, shipment.stages[0].id, product_id=1, quantity=Decimal("10"))
        dispatch.reserve_stage(employee_id, shipment.stages[0].id)
        dispatch.ship_stage(employee_id, shipment.stages[0].id)

    Работать можно только с этапами, которые уходят со склада сотрудника.
    """

    # ---------- Данные для форм ----------

    @abstractmethod
    def list_warehouses(self, employee_id: int) -> list[WarehouseDTO]:
        """Все действующие склады — для выбора маршрута."""

    @abstractmethod
    def list_available_stock(self, employee_id: int) -> list[StockItemDTO]:
        """Товары на складе сотрудника, которые можно отправить (есть свободный остаток)."""

    @abstractmethod
    def list_drivers(self, employee_id: int) -> list[EmployeeDTO]:
        """Сотрудники склада сотрудника — для выбора водителя."""

    @abstractmethod
    def list_outgoing(self, employee_id: int, only_active: bool = True) -> list[StageDTO]:
        """Этапы, которые уходят со склада сотрудника.

        only_active=True — только Черновик, В ожидании, Зарезервировано, Отправлено.
        Товары (items) не заполняются.
        """

    # ---------- Черновик ----------

    @abstractmethod
    def create_draft(
        self,
        employee_id: int,
        planned_date: date,
        route: Sequence[int],
        items: Sequence[NewStageItem] = (),
    ) -> ShipmentDTO:
        """Создаёт перевозку-черновик по маршруту.

        route — id складов по порядку, первый — склад сотрудника.
        items — товары первого этапа (можно добавить и позже через add_item).
        Этап 1 — «Черновик», этапы 2..N — «В ожидании».
        """

    @abstractmethod
    def add_item(
        self, employee_id: int, stage_id: int, product_id: int, quantity: Decimal
    ) -> None:
        """Добавляет товар в этап-черновик. Товар уже есть — заменяет количество."""

    @abstractmethod
    def remove_item(self, employee_id: int, item_id: int) -> None:
        """Убирает позицию из этапа-черновика."""

    @abstractmethod
    def assign_driver(self, employee_id: int, stage_id: int, driver_id: int | None) -> None:
        """Назначает водителя на неотправленный этап. None — снять водителя."""

    @abstractmethod
    def delete_draft(self, employee_id: int, shipment_id: int) -> None:
        """Удаляет перевозку-черновик целиком (этапы и товары каскадом)."""

    # ---------- Резерв и отправка ----------

    @abstractmethod
    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Резервирует товары первого этапа на складе отправления.

        Этап -> «Зарезервировано». Не хватает остатка -> InvalidStatusError.
        """

    @abstractmethod
    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        """Отправляет зарезервированный этап.

        Списывает товар со склада отправления (остаток и резерв),
        этап и перевозка -> «Отправлено».
        """

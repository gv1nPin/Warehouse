from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from warehouse.common.dto import (
    EmployeeDTO,
    NewStageDocument,
    NewStageItem,
    ShipmentDTO,
    StageDocumentDTO,
    StageDTO,
    StockItemDTO,
    WarehouseDTO,
)


class AbstractShipmentDraftService(ABC):
    """Черновик перевозки: маршрут, товары, водитель — всё, что правится
    до того, как ShipmentDispatchService начнёт резервировать и отправлять товар.

    Транзакцию открывает сам, поэтому вызывается прямо из web:

        draft = draft_service.create_draft(employee_id, date(2026, 10, 1), [1, 2, 3])
        draft_service.add_item(
            employee_id, draft.stages[0].id, product_id=1, quantity=Decimal("10")
        )
        # дальше эстафету принимает ShipmentDispatchService:
        # dispatch_service.reserve_stage(employee_id, draft.stages[0].id)
        # dispatch_service.ship_stage(employee_id, draft.stages[0].id)

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
        """Водители склада сотрудника (роль «Водитель») — для выбора водителя."""

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
        driver_id: int | None = None,
        documents: Sequence[NewStageDocument] = (),
    ) -> ShipmentDTO:
        """Создаёт перевозку-черновик по маршруту.

        route — id складов по порядку, первый — склад сотрудника.
        items — товары первого этапа (можно добавить и позже через add_item).
        driver_id — водитель первого этапа (можно назначить позже через assign_driver).
        documents — файлы, уже сохранённые web-слоем (можно прикрепить позже
        через attach_document). Без документа этап не зарезервировать.
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

    # ---------- Документы ----------

    @abstractmethod
    def attach_document(
        self, employee_id: int, stage_id: int, document: NewStageDocument
    ) -> StageDocumentDTO:
        """Прикрепляет документ к этапу-черновику.

        Файл сохраняет web-слой, сюда приходят только его данные.
        Этап не первый или не «Черновик» -> InvalidStatusError.
        """

    @abstractmethod
    def remove_document(self, employee_id: int, document_id: int) -> StageDocumentDTO:
        """Открепляет документ от этапа-черновика и возвращает его. Файл на диске удаляет web-слой."""

import logging
from collections.abc import Callable, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation

from warehouse.api.dto import (
    EmployeeDTO,
    NewStage,
    NewStageItem,
    ShipmentDTO,
    StageDTO,
    StockItemDTO,
    WarehouseDTO,
)
from warehouse.bll.interfaces.auth_service import AbstractAccessService
from warehouse.bll.interfaces.shipment_service.abstract_shipment_draft_service import (
    AbstractShipmentDraftService,
)
from warehouse.common import StatusName
from warehouse.common.exceptions import (
    InvalidStatusError,
    NotFoundError,
    ValidationError,
)
from warehouse.dal.unit_of_work import UnitOfWork

from ._sender_guards import SenderGuardsMixin

# Этап ещё не принят — его видно в «Исходящих».
ACTIVE_STATUSES = (
    StatusName.DRAFT,
    StatusName.WAITING,
    StatusName.RESERVED,
    StatusName.SHIPPED,
)

# Пока груз не уехал, водителя можно менять.
NOT_SHIPPED_STATUSES = (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)


class ShipmentDraftService(SenderGuardsMixin, AbstractShipmentDraftService):
    """Черновик перевозки со склада сотрудника: маршрут, товары, водитель.

    Товары вручную заводятся только в первый этап. Этапы 2..N заполняет
    ShipmentTransitCoordinator после приёмки предыдущего: дальше едет факт.

    Готовый этап дальше ведёт ShipmentDispatchService (резерв и отправка) —
    этот сервис его не трогает.

    Проверяем в порядке «кто → куда → что», как и в приёмке.
    Транзакцию открывает сам, поэтому вызывается прямо из web.
    """

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    # ---------- Данные для форм ----------

    def list_warehouses(self, employee_id: int) -> list[WarehouseDTO]:
        with self._uow_factory() as uow:
            self._sender(uow, employee_id)
            return uow.warehouses.list_active()

    def list_available_stock(self, employee_id: int) -> list[StockItemDTO]:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            return uow.stock.list_available(actor.employee.warehouse_id)

    def list_drivers(self, employee_id: int) -> list[EmployeeDTO]:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            return uow.employees.list_by_warehouse(actor.employee.warehouse_id)

    def list_outgoing(self, employee_id: int, only_active: bool = True) -> list[StageDTO]:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            status_ids = self._status_ids(uow, ACTIVE_STATUSES) if only_active else None
            return uow.stages.list_outgoing(
                warehouse_id=actor.employee.warehouse_id, status_ids=status_ids
            )

    # ---------- Черновик ----------

    def create_draft(
        self,
        employee_id: int,
        planned_date: date,
        route: Sequence[int],
        items: Sequence[NewStageItem] = (),
    ) -> ShipmentDTO:
        route = list(route)
        items = [
            NewStageItem(product_id=i.product_id, quantity=self._to_quantity(i.quantity))
            for i in items
        ]

        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)

            if len(route) < 2:
                raise ValidationError("В маршруте должно быть минимум два склада")
            self._access.require_warehouse(actor, route[0])
            if planned_date < date.today():
                raise ValidationError("Плановая дата не может быть в прошлом")
            for from_id, to_id in zip(route, route[1:]):
                if from_id == to_id:
                    raise ValidationError("Соседние склады маршрута не должны совпадать")
            for warehouse_id in set(route):
                if uow.warehouses.get_by_id(warehouse_id) is None:
                    raise NotFoundError(f"Склад №{warehouse_id} не найден")

            if len({i.product_id for i in items}) != len(items):
                raise ValidationError("Один товар добавлен в этап дважды")
            for item in items:
                self._require_available(uow, route[0], item.product_id, item.quantity)

            # Товары заводим только в первый этап, остальные заполнит транзит.
            stages = [
                NewStage(
                    from_warehouse_id=from_id,
                    to_warehouse_id=to_id,
                    items=tuple(items) if order == 0 else (),
                )
                for order, (from_id, to_id) in enumerate(zip(route, route[1:]))
            ]

            draft_id = self._status_id(uow, StatusName.DRAFT)
            shipment_id = uow.shipments.create(
                creator_id=actor.employee.id,
                planned_date=planned_date,
                status_id=draft_id,
                stages=stages,
                stage_status_id=self._status_id(uow, StatusName.WAITING),
            )
            # Репозиторий ставит всем этапам один статус, а первый — черновик.
            first = uow.stages.get_by_order(shipment_id, 1)
            uow.stages.set_status(first.id, draft_id)

            logging.info(
                "Сотрудник №%s создал черновик перевозки №%s по маршруту %s",
                actor.employee.id,
                shipment_id,
                route,
            )
            return self._shipment(uow, shipment_id)

    def add_item(
        self, employee_id: int, stage_id: int, product_id: int, quantity: Decimal
    ) -> None:
        quantity = self._to_quantity(quantity)

        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._editable_stage(uow, actor, stage_id)

            if uow.products.get_by_id(product_id) is None:
                raise NotFoundError(f"Товар №{product_id} не найден")
            self._require_available(uow, stage.from_warehouse.id, product_id, quantity)

            existing = next((i for i in stage.items if i.product_id == product_id), None)
            if existing is None:
                uow.stage_items.add(stage_id, product_id, quantity)
            else:
                uow.stage_items.set_document_quantity(existing.id, quantity)

    def remove_item(self, employee_id: int, item_id: int) -> None:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)

            item = uow.stage_items.get_by_id(item_id)
            if item is None:
                raise NotFoundError(f"Позиция №{item_id} не найдена")

            self._editable_stage(uow, actor, item.stage_id)
            uow.stage_items.delete(item_id)

    def assign_driver(self, employee_id: int, stage_id: int, driver_id: int | None) -> None:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._stage_from_my_warehouse(uow, actor, stage_id)

            if stage.status_id not in self._status_ids(uow, NOT_SHIPPED_STATUSES):
                raise InvalidStatusError(
                    f"Этап в статусе «{stage.status_name}»: водителя уже не поменять"
                )

            if driver_id is not None:
                driver = uow.employees.get_by_id(driver_id)
                if driver is None:
                    raise NotFoundError(f"Сотрудник №{driver_id} не найден или заблокирован")
                if driver.warehouse_id != stage.from_warehouse.id:
                    raise ValidationError("Водитель должен работать на складе отправления")

            uow.stages.assign_driver(stage_id, driver_id)

    def delete_draft(self, employee_id: int, shipment_id: int) -> None:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)

            shipment = uow.shipments.get_by_id(shipment_id)
            if shipment is None:
                raise NotFoundError(f"Перевозка №{shipment_id} не найдена")

            self._access.require_warehouse(actor, shipment.stages[0].from_warehouse.id)
            if shipment.status_id != self._status_id(uow, StatusName.DRAFT):
                raise InvalidStatusError(
                    f"Перевозка в статусе «{shipment.status_name}»: удалить можно только черновик"
                )

            uow.shipments.delete(shipment_id)
            logging.info(
                "Сотрудник №%s удалил черновик перевозки №%s", actor.employee.id, shipment_id
            )

    # ---------- Утилиты ----------

    @staticmethod
    def _shipment(uow: UnitOfWork, shipment_id: int) -> ShipmentDTO:
        shipment = uow.shipments.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Перевозка №{shipment_id} не найдена")
        return shipment

    @staticmethod
    def _require_available(
        uow: UnitOfWork, warehouse_id: int, product_id: int, quantity: Decimal
    ) -> None:
        """Предварительная проверка без блокировки: окончательно проверит reserve_stage."""
        row = uow.stock.get(warehouse_id, product_id)
        available = row.available if row is not None else Decimal(0)
        if available < quantity:
            raise ValidationError(
                f"На складе свободно {available}, а в этап добавляется {quantity}"
            )

    @staticmethod
    def _to_quantity(quantity: Decimal) -> Decimal:
        """Приводит количество к Decimal: из web оно приходит числом или строкой."""
        try:
            value = quantity if isinstance(quantity, Decimal) else Decimal(str(quantity))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Количество должно быть числом") from None

        if not value.is_finite() or value <= 0:
            raise ValidationError("Количество должно быть больше нуля")
        return value

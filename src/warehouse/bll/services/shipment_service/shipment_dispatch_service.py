import logging
from collections.abc import Callable, Collection, Sequence
from datetime import date, datetime, timezone
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
from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.bll.interfaces.shipment_service.abstract_shipment_dispatch_service import (
    AbstractShipmentDispatchService,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import (
    InvalidStatusError,
    NotFoundError,
    ValidationError,
)
from warehouse.dal.unit_of_work import UnitOfWork

# Этап ещё не принят — его видно в «Исходящих».
ACTIVE_STATUSES = (
    StatusName.DRAFT,
    StatusName.WAITING,
    StatusName.RESERVED,
    StatusName.SHIPPED,
)

# Пока груз не уехал, водителя можно менять.
NOT_SHIPPED_STATUSES = (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)


class ShipmentDispatchService(AbstractShipmentDispatchService):
    """Отправка груза со склада сотрудника.

    Товары вручную заводятся только в первый этап. Этапы 2..N заполняет
    ShipmentTransitCoordinator после приёмки предыдущего: дальше едет факт.

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

    # ---------- Резерв и отправка ----------

    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._editable_stage(uow, actor, stage_id)

            if not stage.items:
                raise ValidationError("В этапе нет ни одной позиции")

            warehouse_id = stage.from_warehouse.id
            # for_update блокирует строки до конца транзакции, чтобы двое
            # не зарезервировали один и тот же товар одновременно.
            stock = uow.stock.get_many(
                warehouse_id, (item.product_id for item in stage.items), for_update=True
            )
            for item in stage.items:
                row = stock.get(item.product_id)
                available = row.available if row is not None else Decimal(0)
                if available < item.document_quantity:
                    raise InvalidStatusError(
                        f"На складе свободно {available} {item.measurement_name} "
                        f"товара «{item.product_name}», а нужно {item.document_quantity}"
                    )
                uow.stock.change(
                    warehouse_id=warehouse_id,
                    product_id=item.product_id,
                    reserved_delta=item.document_quantity,
                )

            reserved_id = self._status_id(uow, StatusName.RESERVED)
            uow.stages.set_status(stage_id, reserved_id)
            uow.shipments.set_status(stage.shipment_id, reserved_id)

            logging.info(
                "Сотрудник №%s зарезервировал этап №%s на складе №%s",
                actor.employee.id,
                stage_id,
                warehouse_id,
            )
            return self._stage(uow, stage_id)

    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._stage_from_my_warehouse(uow, actor, stage_id)
            self._require_status(uow, stage, StatusName.RESERVED)

            if not stage.items:
                raise ValidationError("В этапе нет ни одной позиции")

            warehouse_id = stage.from_warehouse.id
            stock = uow.stock.get_many(
                warehouse_id, (item.product_id for item in stage.items), for_update=True
            )
            for item in stage.items:
                row = stock.get(item.product_id)
                # Резерв делали мы же, так что расхождение здесь — сбой данных,
                # а не ошибка пользователя. Отказываем, пока CHECK в БД не уронил коммит.
                if row is None or row.reserved_quantity < item.document_quantity:
                    raise InvalidStatusError(
                        f"Резерв товара «{item.product_name}» на складе не найден, "
                        f"отправка невозможна"
                    )
                uow.stock.change(
                    warehouse_id=warehouse_id,
                    product_id=item.product_id,
                    quantity_delta=-item.document_quantity,
                    reserved_delta=-item.document_quantity,
                )

            shipped_id = self._status_id(uow, StatusName.SHIPPED)
            uow.stages.set_status(stage_id, shipped_id, sent_at=datetime.now(timezone.utc))
            uow.shipments.set_status(stage.shipment_id, shipped_id)

            logging.info(
                "Сотрудник №%s отправил этап №%s со склада №%s на склад №%s",
                actor.employee.id,
                stage_id,
                warehouse_id,
                stage.to_warehouse.id,
            )
            return self._stage(uow, stage_id)

    # ---------- Проверки ----------

    def _sender(self, uow: UnitOfWork, employee_id: int) -> ActorDTO:
        """Сотрудник с правом отправки. Нет права -> AccessDeniedError."""
        actor = self._access.get_actor(uow, employee_id)
        self._access.require_permission(actor, PermissionName.SHIPMENT_CREATE)
        return actor

    def _stage_from_my_warehouse(
        self, uow: UnitOfWork, actor: ActorDTO, stage_id: int
    ) -> StageDTO:
        """Этап, который уходит со склада сотрудника. Чужой склад -> AccessDeniedError."""
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")

        if actor.employee.warehouse_id != stage.from_warehouse.id:
            logging.warning(
                "Отказ в отправке: сотрудник №%s (склад №%s) обратился к этапу №%s "
                "со склада №%s",
                actor.employee.id,
                actor.employee.warehouse_id,
                stage.id,
                stage.from_warehouse.id,
            )
        self._access.require_warehouse(actor, stage.from_warehouse.id)
        return stage

    def _editable_stage(self, uow: UnitOfWork, actor: ActorDTO, stage_id: int) -> StageDTO:
        """Первый этап в статусе «Черновик» — только его товары правят руками."""
        stage = self._stage_from_my_warehouse(uow, actor, stage_id)
        if stage.stage_order != 1:
            raise InvalidStatusError(
                "Товары этого этапа заполняются автоматически после приёмки предыдущего"
            )
        self._require_status(uow, stage, StatusName.DRAFT)
        return stage

    def _require_status(self, uow: UnitOfWork, stage: StageDTO, status: StatusName) -> None:
        if stage.status_id != self._status_id(uow, status):
            raise InvalidStatusError(
                f"Этап в статусе «{stage.status_name}»: действие доступно "
                f"только в статусе «{status}»"
            )

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

    # ---------- Утилиты ----------

    @staticmethod
    def _shipment(uow: UnitOfWork, shipment_id: int) -> ShipmentDTO:
        shipment = uow.shipments.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Перевозка №{shipment_id} не найдена")
        return shipment

    @staticmethod
    def _stage(uow: UnitOfWork, stage_id: int) -> StageDTO:
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")
        return stage

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

    @staticmethod
    def _status_id(uow: UnitOfWork, status_name: StatusName) -> int:
        status_id = uow.statuses.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

    @staticmethod
    def _status_ids(uow: UnitOfWork, names: Collection[StatusName]) -> list[int]:
        ids = (uow.statuses.get_id(name) for name in names)
        return [status_id for status_id in ids if status_id is not None]

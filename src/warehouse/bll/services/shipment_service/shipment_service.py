"""
ShipmentService — полная реализация сервиса перевозок.
Включает протоколы репозиториев, исключения и бизнес-логику.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Protocol, runtime_checkable

from warehouse.api.dto.employee import EmployeeDTO
from warehouse.api.dto.product import ProductDTO
from warehouse.api.dto.shipment import ShipmentDTO, StageDTO, StageItemDTO
from warehouse.api.dto.warehouse import StockItemDTO
from warehouse.api.dto.warehouse import WarehouseDTO
from warehouse.common.exceptions import (
    AccessDeniedError,
    BusinessError,
    InvalidStatusError,
    NotFoundError,
    ValidationError,
)
from warehouse.bll.interfaces.shipment_service.shipment_service_abc import ShipmentServiceABC


# ──────────────────────────────────────────────────────────────────
# Статусы
# ──────────────────────────────────────────────────────────────────

STATUS_DRAFT = "Черновик"
STATUS_PENDING = "В ожидании"
STATUS_RESERVED = "Зарезервировано"
STATUS_SHIPPED = "Отправлено"


# ──────────────────────────────────────────────────────────────────
# Протоколы репозиториев (структурная типизация)
# ──────────────────────────────────────────────────────────────────

@runtime_checkable
class EmployeeRepo(Protocol):
    def get_by_id(self, employee_id: int) -> EmployeeDTO | None: ...


@runtime_checkable
class StockRepo(Protocol):
    def list_available(self, warehouse_id: int) -> list[StockItemDTO]: ...
    def get_one(self, warehouse_id: int, product_id: int) -> StockItemDTO | None: ...
    def get_many(
        self,
        warehouse_id: int,
        product_ids: list[int],
        for_update: bool = False,
    ) -> list[StockItemDTO]: ...
    def decrease_quantity(
        self,
        warehouse_id: int,
        product_id: int,
        amount: Decimal,
    ) -> None: ...
    def decrease_quantity_and_reserved(
        self,
        warehouse_id: int,
        product_id: int,
        quantity: Decimal,
        reserved: Decimal,
    ) -> None: ...


@runtime_checkable
class ShipmentRepo(Protocol):
    def get_by_id(self, shipment_id: int) -> ShipmentDTO | None: ...
    def list_by_creator(self, creator_id: int) -> list[ShipmentDTO]: ...
    def create(
        self,
        creator_id: int,
        planned_date: date,
        status_name: str,
    ) -> ShipmentDTO: ...
    def update_status(self, shipment_id: int, status_name: str) -> None: ...
    def delete(self, shipment_id: int) -> None: ...


@runtime_checkable
class StageRepo(Protocol):
    def get_by_id(self, stage_id: int) -> StageDTO | None: ...
    def get_first_stage_for_shipment(self, shipment_id: int) -> StageDTO | None: ...
    def get_for_update(self, stage_id: int) -> StageDTO | None: ...
    def create(
        self,
        shipment_id: int,
        stage_order: int,
        planned_date: date,
        from_warehouse_id: int,
        to_warehouse_id: int,
        status_name: str,
        creator_id: int,
    ) -> StageDTO: ...
    def assign_driver(self, stage_id: int, driver_id: int | None) -> None: ...
    def mark_as_shipped(self, stage_id: int, sent_at: datetime) -> None: ...


@runtime_checkable
class StageItemRepo(Protocol):
    def get_by_id(self, item_id: int) -> StageItemDTO | None: ...
    def list_for_stage(self, stage_id: int) -> list[StageItemDTO]: ...
    def find_by_stage_and_product(
        self,
        stage_id: int,
        product_id: int,
    ) -> StageItemDTO | None: ...
    def add(
        self,
        stage_id: int,
        product_id: int,
        quantity: Decimal,
    ) -> int: ...
    def update_quantity(self, item_id: int, quantity: Decimal) -> None: ...
    def set_document_quantity(self, item_id: int, quantity: Decimal) -> None: ...
    def delete(self, item_id: int) -> None: ...


@runtime_checkable
class WarehouseRepo(Protocol):
    def get_by_id(self, warehouse_id: int) -> WarehouseDTO | None: ...
    def exists(self, warehouse_id: int) -> bool: ...


@runtime_checkable
class ProductRepo(Protocol):
    def get_by_id(self, product_id: int) -> ProductDTO | None: ...
    def exists(self, product_id: int) -> bool: ...


# ──────────────────────────────────────────────────────────────────
# Сервис
# ──────────────────────────────────────────────────────────────────

class ShipmentService(ShipmentServiceABC):
    """Полная реализация сервиса перевозок."""

    def __init__(
        self,
        employees: EmployeeRepo,
        stock: StockRepo,
        shipments: ShipmentRepo,
        stages: StageRepo,
        stage_items: StageItemRepo,
        warehouses: WarehouseRepo,
        products: ProductRepo,
    ) -> None:
        self._employees = employees
        self._stock = stock
        self._shipments = shipments
        self._stages = stages
        self._stage_items = stage_items
        self._warehouses = warehouses
        self._products = products

    # ── Вспомогательные ───────────────────────────────────────────

    def _get_employee(self, employee_id: int) -> EmployeeDTO:
        emp = self._employees.get_by_id(employee_id)
        if emp is None:
            raise NotFoundError(f"Сотрудник {employee_id} не найден.")
        return emp

    def _get_shipment(self, shipment_id: int) -> ShipmentDTO:
        shipment = self._shipments.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Перевозка {shipment_id} не найдена.")
        return shipment

    def _get_stage(self, stage_id: int) -> StageDTO:
        stage = self._stages.get_by_id(stage_id)
        if stage is None:
            raise NotFoundError(f"Этап {stage_id} не найден.")
        return stage

    def _get_item(self, item_id: int) -> StageItemDTO:
        item = self._stage_items.get_by_id(item_id)
        if item is None:
            raise NotFoundError(f"Строка документа {item_id} не найдена.")
        return item

    @staticmethod
    def _validate_quantity(quantity: Decimal) -> None:
        if quantity <= 0:
            raise ValidationError("Количество должно быть больше 0.")
        if -quantity.as_tuple().exponent > 3:
            raise ValidationError("Количество не должно иметь более 3 знаков после запятой.")

    def _check_draft(self, shipment: ShipmentDTO) -> None:
        if shipment.status_name != STATUS_DRAFT:
            raise InvalidStatusError(
                "Действие доступно только для перевозки в статусе «Черновик»."
            )

    def _check_own_warehouse(self, employee: EmployeeDTO, stage: StageDTO) -> None:
        if stage.from_warehouse.id != employee.warehouse_id:
            raise AccessDeniedError("Этап должен находиться на складе сотрудника.")

    # ── get_available_stock ───────────────────────────────────────

    def get_available_stock(self, employee_id: int) -> list[StockItemDTO]:
        emp = self._get_employee(employee_id)
        return self._stock.list_available(warehouse_id=emp.warehouse_id)

    # ── get_my_shipments ──────────────────────────────────────────

    def get_my_shipments(self, employee_id: int) -> list[ShipmentDTO]:
        return self._shipments.list_by_creator(creator_id=employee_id)

    # ── create_draft ──────────────────────────────────────────────

    def create_draft(
        self,
        employee_id: int,
        route: list[int],
        planned_date: date,
    ) -> int:
        # Маршрут
        if len(route) < 2:
            raise ValidationError("Маршрут должен содержать не менее 2 складов.")

        emp = self._get_employee(employee_id)

        if route[0] != emp.warehouse_id:
            raise ValidationError(
                "Первый склад маршрута должен совпадать со складом сотрудника."
            )

        if len(set(route)) != len(route):
            raise ValidationError("Склады в маршруте не должны повторяться.")

        for wid in route:
            if not self._warehouses.exists(wid):
                raise NotFoundError(f"Склад {wid} не существует.")

        if planned_date < date.today():
            raise ValidationError("Дата не может быть в прошлом.")

        # Создаём перевозку
        shipment = self._shipments.create(
            creator_id=employee_id,
            planned_date=planned_date,
            status_name=STATUS_DRAFT,
        )

        # Этапы
        for i, (from_id, to_id) in enumerate(zip(route, route[1:])):
            status_name = STATUS_DRAFT if i == 0 else STATUS_PENDING
            self._stages.create(
                shipment_id=shipment.id,
                stage_order=i,
                planned_date=planned_date,
                from_warehouse_id=from_id,
                to_warehouse_id=to_id,
                status_name=status_name,
                creator_id=employee_id,
            )

        return shipment.id

    # ── add_item ──────────────────────────────────────────────────

    def add_item(
        self,
        employee_id: int,
        shipment_id: int,
        product_id: int,
        quantity: Decimal,
    ) -> int:
        self._validate_quantity(quantity)

        shipment = self._get_shipment(shipment_id)
        self._check_draft(shipment)

        emp = self._get_employee(employee_id)
        first_stage = self._stages.get_first_stage_for_shipment(shipment_id)
        if first_stage is None:
            raise NotFoundError("У перевозки нет этапов.")

        self._check_own_warehouse(emp, first_stage)

        if not self._products.exists(product_id):
            raise NotFoundError(f"Товар {product_id} не найден.")

        stock_item = self._stock.get_one(
            warehouse_id=first_stage.from_warehouse.id,
            product_id=product_id,
        )
        if stock_item is None or stock_item.available < quantity:
            raise ValidationError("Недостаточно свободного остатка для добавления товара.")

        existing = self._stage_items.find_by_stage_and_product(
            stage_id=first_stage.id,
            product_id=product_id,
        )
        if existing:
            new_qty = existing.document_quantity + quantity
            if stock_item.available < new_qty:
                raise ValidationError(
                    "Недостаточно свободного остатка для увеличения количества товара."
                )
            self._stage_items.update_quantity(item_id=existing.id, quantity=new_qty)
            return existing.id

        return self._stage_items.add(
            stage_id=first_stage.id,
            product_id=product_id,
            quantity=quantity,
        )

    # ── update_item_quantity ───────────────────────────────────────

    def update_item_quantity(
        self,
        employee_id: int,
        item_id: int,
        quantity: Decimal,
    ) -> None:
        self._validate_quantity(quantity)

        item = self._get_item(item_id)
        stage = self._get_stage(item.stage_id)
        shipment = self._get_shipment(stage.shipment_id)

        self._check_draft(shipment)

        emp = self._get_employee(employee_id)
        self._check_own_warehouse(emp, stage)

        delta = quantity - item.document_quantity
        if delta > 0:
            stock_item = self._stock.get_one(
                warehouse_id=stage.from_warehouse.id,
                product_id=item.product_id,
            )
            if stock_item is None or stock_item.available < delta:
                raise ValidationError("Недостаточно свободного остатка.")

        self._stage_items.set_document_quantity(item_id=item_id, quantity=quantity)

    # ── remove_item ────────────────────────────────────────────────

    def remove_item(self, employee_id: int, item_id: int) -> None:
        item = self._get_item(item_id)
        stage = self._get_stage(item.stage_id)
        shipment = self._get_shipment(stage.shipment_id)

        self._check_draft(shipment)

        emp = self._get_employee(employee_id)
        self._check_own_warehouse(emp, stage)

        self._stage_items.delete(item_id=item_id)

    # ── assign_driver ─────────────────────────────────────────────

    def assign_driver(
        self,
        employee_id: int,
        stage_id: int,
        driver_id: Optional[int],
    ) -> None:
        stage = self._get_stage(stage_id)
        shipment = self._get_shipment(stage.shipment_id)

        if stage.sent_at is not None:
            raise InvalidStatusError("Нельзя назначить водителя на отправленный этап.")

        emp = self._get_employee(employee_id)
        self._check_own_warehouse(emp, stage)

        self._stages.assign_driver(stage_id=stage_id, driver_id=driver_id)

    # ── delete_draft ──────────────────────────────────────────────

    def delete_draft(self, employee_id: int, shipment_id: int) -> None:
        shipment = self._get_shipment(shipment_id)

        if shipment.creator_id != employee_id:
            raise AccessDeniedError("Удалять черновик может только его создатель.")

        self._check_draft(shipment)

        self._shipments.delete(shipment_id=shipment_id)

    # ── ship_stage ────────────────────────────────────────────────

    def ship_stage(self, employee_id: int, stage_id: int) -> None:
        stage = self._stages.get_for_update(stage_id)
        if stage is None:
            raise NotFoundError(f"Этап {stage_id} не найден.")

        if stage.status_name not in (STATUS_DRAFT, STATUS_RESERVED):
            raise InvalidStatusError(
                "Отправлять можно только этапы со статусом «Черновик» или «Зарезервировано»."
            )

        emp = self._get_employee(employee_id)
        self._check_own_warehouse(emp, stage)

        items = self._stage_items.list_for_stage(stage_id)
        if not items:
            raise ValidationError("В этапе нет товаров — нельзя отправить.")

        # Блокируем строки остатков
        wh_id = stage.from_warehouse.id
        product_ids = [i.product_id for i in items]
        stocks = self._stock.get_many(
            warehouse_id=wh_id,
            product_ids=product_ids,
            for_update=True,
        )
        stock_map = {s.product_id: s for s in stocks}

        for item in items:
            stock = stock_map.get(item.product_id)
            if stock is None:
                raise ValidationError(
                    f"Нет данных об остатках для товара {item.product_id}"
                )

            if stage.status_name == STATUS_DRAFT:
                if stock.available < item.document_quantity:
                    raise ValidationError(
                        f"Недостаточно свободного остатка для товара {item.product_id}."
                    )
                self._stock.decrease_quantity(
                    warehouse_id=wh_id,
                    product_id=item.product_id,
                    amount=item.document_quantity,
                )
            elif stage.status_name == STATUS_RESERVED:
                if stock.reserved_quantity < item.document_quantity:
                    raise ValidationError(
                        f"Недостаточно зарезервированного количества для товара {item.product_id}."
                    )
                self._stock.decrease_quantity_and_reserved(
                    warehouse_id=wh_id,
                    product_id=item.product_id,
                    quantity=item.document_quantity,
                    reserved=item.document_quantity,
                )

        now = datetime.utcnow()
        self._stages.mark_as_shipped(stage_id=stage_id, sent_at=now)
        self._shipments.update_status(
            shipment_id=stage.shipment_id,
            status_name=STATUS_SHIPPED,
        )

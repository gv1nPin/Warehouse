"""Простые объекты, которые репозитории отдают наружу вместо моделей SQLAlchemy.

Они не привязаны к сессии, поэтому их можно спокойно передавать в BLL и WEB.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


# ---------- Результаты ----------

@dataclass(frozen=True, slots=True)
class EmployeeDTO:
    id: int
    first_name: str
    last_name: str
    login: str
    role_id: int
    role_name: str
    warehouse_id: int
    is_deleted: bool

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}"


@dataclass(frozen=True, slots=True)
class EmployeeAuthDTO:
    employee: EmployeeDTO
    password_hash: str


@dataclass(frozen=True, slots=True)
class WarehouseDTO:
    id: int
    title: str
    address: str


@dataclass(frozen=True, slots=True)
class StockItemDTO:
    warehouse_id: int
    product_id: int
    article_number: str
    product_name: str
    measurement_name: str
    quantity: Decimal
    reserved_quantity: Decimal

    @property
    def available(self) -> Decimal:
        return self.quantity - self.reserved_quantity


@dataclass(frozen=True, slots=True)
class StageItemDTO:
    id: int
    product_id: int
    article_number: str
    product_name: str
    measurement_name: str
    document_quantity: Decimal
    actual_quantity: Decimal | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class RouteDTO:
    """Один путь = один этап отгрузки (ShipmentStages)."""

    stage_id: int
    shipment_id: int
    stage_order: int
    status_name: str
    shipment_status_name: str
    planned_date: date
    creator_id: int
    from_warehouse: WarehouseDTO
    to_warehouse: WarehouseDTO
    driver_id: int | None
    driver_name: str | None
    acceptor_id: int | None
    sent_at: datetime | None
    received_at: datetime | None
    items: tuple[StageItemDTO, ...] = ()


@dataclass(frozen=True, slots=True)
class ShipmentDTO:
    id: int
    status_name: str
    planned_date: date
    created_at: datetime
    creator_id: int
    creator_name: str
    stages: tuple[RouteDTO, ...]


# ---------- Входные данные ----------

@dataclass(frozen=True, slots=True)
class NewStageItem:
    product_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class NewStage:
    from_warehouse_id: int
    to_warehouse_id: int
    items: tuple[NewStageItem, ...]
    driver_id: int | None = None

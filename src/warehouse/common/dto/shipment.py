from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from .warehouse import WarehouseDTO


# ---------- Результаты ----------

@dataclass(frozen=True, slots=True)
class StageItemDTO:
    id: int
    stage_id: int
    product_id: int
    article_number: str
    product_name: str
    measurement_name: str
    document_quantity: Decimal
    actual_quantity: Decimal | None
    comment: str | None


@dataclass(frozen=True, slots=True)
class StageDTO:
    """Один путь = один этап отгрузки (ShipmentStages)."""

    id: int
    shipment_id: int
    stage_order: int
    status_id: int
    status_name: str
    shipment_status_id: int
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
    status_id: int
    status_name: str
    planned_date: date
    created_at: datetime
    creator_id: int
    creator_name: str
    stages: tuple[StageDTO, ...]


@dataclass(frozen=True, slots=True)
class StageDocumentDTO:
    id: int
    stage_id: int
    file_name: str
    storage_path: str
    content_type: str | None
    size_bytes: int | None
    uploaded_by: int
    uploaded_by_name: str
    uploaded_at: datetime


# ---------- Входные данные ----------

@dataclass(frozen=True, slots=True)
class NewStageItem:
    product_id: int
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class NewStageDocument:
    """Файл, который web-слой уже сохранил. BLL записывает только его данные."""

    file_name: str
    storage_path: str
    content_type: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class NewStage:
    from_warehouse_id: int
    to_warehouse_id: int
    items: tuple[NewStageItem, ...] = ()
    driver_id: int | None = None

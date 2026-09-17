"""Все запросы в БД. Один репозиторий = одна сущность."""

from .base_repository import BaseRepository
from .employee_repository import EmployeeRepository
from .measurement_repository import MeasurementRepository
from .product_repository import ProductRepository
from .role_repository import RoleRepository
from .shipment_repository import ShipmentRepository
from .shipment_stage_repository import ShipmentStageRepository
from .stage_item_repository import StageItemRepository
from .status_repository import StatusRepository
from .stock_repository import StockRepository
from .warehouse_repository import WarehouseRepository

__all__ = [
    "BaseRepository",
    "EmployeeRepository",
    "MeasurementRepository",
    "ProductRepository",
    "RoleRepository",
    "ShipmentRepository",
    "ShipmentStageRepository",
    "StageItemRepository",
    "StatusRepository",
    "StockRepository",
    "WarehouseRepository",
]

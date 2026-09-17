"""Модели SQLAlchemy. Импортируются все сразу, чтобы связи (relationship) по строковым именам находили друг друга."""

from .base import Base
from .employee import Employee
from .operation_history import OperationHistory
from .product import Product
from .reference import Measurement, Permission, Role, RolePermission, Status
from .shipment import Shipment, ShipmentStage, StageItem
from .stock import StockOnWarehouse
from .warehouse import Warehouse

__all__ = [
    "Base",
    "Employee",
    "Measurement",
    "OperationHistory",
    "Permission",
    "Product",
    "Role",
    "RolePermission",
    "Shipment",
    "ShipmentStage",
    "StageItem",
    "Status",
    "StockOnWarehouse",
    "Warehouse",
]

from warehouse.dal.entities.base import Base

# 2. Импортируем все модели из их новых персональных файлов
from warehouse.dal.entities.warehouses import RolePermission, Role, Permission, Warehouse
from warehouse.dal.entities.employees import Employee
from warehouse.dal.entities.products import Product, StockOnWarehouse
from warehouse.dal.entities.shipments import Shipment, ShipmentStage, StageItem

# 3. Экспортируем всё наружу единым списком
__all__ = [
    "Base",
    "RolePermission",
    "Role",
    "Permission",
    "Warehouse",
    "Employee",
    "Product",
    "StockOnWarehouse",
    "Shipment",
    "ShipmentStage",
    "StageItem",
]

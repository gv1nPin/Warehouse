from Warehouse.DAL.Entities.Base import Base

# 2. Импортируем все модели из их новых персональных файлов
from Warehouse.DAL.Entities.Warehouses import RolePermission, Role, Permission, Warehouse
from Warehouse.DAL.Entities.Employees import Employee
from Warehouse.DAL.Entities.Products import Product, StockOnWarehouse
from Warehouse.DAL.Entities.Shipments import Shipment, ShipmentStage, StageItem

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

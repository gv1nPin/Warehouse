"""Простые объекты, которые репозитории отдают наружу вместо моделей SQLAlchemy.

Они не привязаны к сессии, поэтому их можно спокойно передавать в BLL и WEB.
DTO ссылаются только на другие DTO и никогда на Entities.
"""

from .employee import EmployeeAuthDTO, EmployeeDTO
from .product import ProductDTO
from .shipment import NewStage, NewStageItem, ShipmentDTO, StageDTO, StageItemDTO
from .warehouse import StockItemDTO, WarehouseDTO

__all__ = [
    "EmployeeAuthDTO",
    "EmployeeDTO",
    "NewStage",
    "NewStageItem",
    "ProductDTO",
    "ShipmentDTO",
    "StageDTO",
    "StageItemDTO",
    "StockItemDTO",
    "WarehouseDTO",
]

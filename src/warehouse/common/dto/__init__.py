"""Простые объекты, которые репозитории отдают наружу вместо моделей SQLAlchemy.

Они не привязаны к сессии, поэтому их можно спокойно передавать в BLL и WEB.
DTO ссылаются только на другие DTO и никогда на Entities.
"""

from .employee import EmployeeAuthDTO, EmployeeDTO, NewEmployee, RoleDTO
from .operation_history import OperationHistoryDTO
from .warehouse import StockItemDTO, WarehouseDTO
from .product import ProductDTO
from .shipment import (
    NewStage,
    NewStageDocument,
    NewStageItem,
    ShipmentDTO,
    StageDocumentDTO,
    StageDTO,
    StageItemDTO,
)

__all__ = [
    "EmployeeAuthDTO",
    "EmployeeDTO",
    "NewEmployee",
    "NewStage",
    "NewStageDocument",
    "NewStageItem",
    "ProductDTO",
    "RoleDTO",
    "ShipmentDTO",
    "StageDocumentDTO",
    "StageDTO",
    "StageItemDTO",
    "StockItemDTO",
    "WarehouseDTO",
    "OperationHistoryDTO"
]

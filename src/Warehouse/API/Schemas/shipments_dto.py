from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal

# --- ВХОДНЫЕ DTO (Запросы от клиента) ---

class ShipmentDraftCreateInputDTO(BaseModel):
    """Входной DTO для планирования маршрута перевозки."""
    planned_date: date = Field(..., description="Планируемая дата отправки цепочки")
    route_warehouses: List[int] = Field(..., min_length=2, description="Список ID складов маршрута в порядке следования") # Опечатка исправлена

class ItemToStageAddInputDTO(BaseModel):
    """Входной DTO для добавления товара в черновик этапа."""
    stage_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    document_quantity: Decimal = Field(..., gt=0, decimal_places=3, description="Вес/количество по документам")

class ActualQuantityInputDTO(BaseModel):
    """Входной DTO для внесения факта пересчета товара при приемке."""
    actual_quantity: Decimal = Field(..., ge=0, decimal_places=3, description="Фактически обнаруженный вес")

# --- ВЫХОДНЫЕ DTO (Ответы сервера клиенту) ---

class IncomingStageOutputDTO(BaseModel):
    """Выходной DTO для вывода списка ожидаемых на складе грузов."""
    stage_id: int
    shipment_id: int
    stage_order: int
    planned_date: Optional[date]
    sent_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class BaseActionResponseDTO(BaseModel):
    """Универсальный DTO для успешных статусных ответов."""
    status: str = "success"
    message: Optional[str] = None

from datetime import datetime
from typing import Any

# Используем современные аннотации
from sqlalchemy import ForeignKey, Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from .base import Base

class OperationHistory(Base):
    __tablename__ = "operation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ФИКС: Точное совпадение с именем таблицы "Employees" (с заглавной буквы)
    employee_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("Employees.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True
    )
    
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # ФИКС: Современный синтаксис Python 3.10+ (int | None вместо Optional[int])
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # ФИКС: Современный синтаксис (dict вместо Dict)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

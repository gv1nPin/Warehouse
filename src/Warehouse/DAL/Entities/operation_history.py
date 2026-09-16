from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import ForeignKey, Integer, String, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from warehouse.dal.database import Base

class OperationHistory(Base):
    __tablename__ = "operation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь со строгим регистром таблицы Employees из pgAdmin
    employee_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("Employees.id", ondelete="RESTRICT"), 
        nullable=False,
        index=True
    )
    
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Слепок изменений (используем JSONБ на уровне Postgres через JSON-абстракцию)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

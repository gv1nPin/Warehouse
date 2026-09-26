from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Identity, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from warehouse.dal.entities.employee import Employee


class OperationHistory(Base):
    """Запись журнала операций: кто, что и над чем сделал."""

    __tablename__ = "operation_history"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("Employees.id", ondelete="RESTRICT"), index=True
    )
    operation_type: Mapped[str] = mapped_column(String(50), index=True)
    entity_name: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int | None]
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    employee: Mapped["Employee"] = relationship()

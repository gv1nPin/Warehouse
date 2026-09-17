from typing import TYPE_CHECKING

from sqlalchemy import Identity, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from warehouse.dal.entities.employee import Employee
    from warehouse.dal.entities.stock import StockOnWarehouse


class Warehouse(Base):
    __tablename__ = "Warehouses"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    employees: Mapped[list["Employee"]] = relationship(back_populates="warehouse")
    stock: Mapped[list["StockOnWarehouse"]] = relationship(back_populates="warehouse")

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Identity, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from warehouse.dal.entities.reference import Role
    from warehouse.dal.entities.warehouse import Warehouse


class Employee(Base):
    __tablename__ = "Employees"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    login: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), index=True)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    warehouse: Mapped["Warehouse"] = relationship(back_populates="employees")
    role: Mapped["Role"] = relationship(back_populates="employees")

    @property
    def full_name(self) -> str:
        return f"{self.last_name} {self.first_name}"

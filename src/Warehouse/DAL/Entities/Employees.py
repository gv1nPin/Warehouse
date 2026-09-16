from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from warehouse.DAL.entities.base import Base
from warehouse.DAL.entities.Warehouses import warehouse, Role


class Employee(Base):
    __tablename__ = "Employees"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    login: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    
    warehouse: Mapped["Warehouse"] = relationship()
    role: Mapped["Role"] = relationship()

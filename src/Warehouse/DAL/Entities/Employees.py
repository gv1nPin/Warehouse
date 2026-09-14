from sqlalchemy import String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from Warehouse.DAL.Entities.Base import Base

class Employee(Base):
    __tablename__ = "Employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    # Связи будут работать, даже если классы в разных файлах (SQLAlchemy найдет их по строковым именам)
    warehouse: Mapped["Warehouse"] = relationship()
    role: Mapped["Role"] = relationship()

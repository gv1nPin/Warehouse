from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    ForeignKey, String, Boolean, Numeric, DateTime, Date
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# Промежуточная таблица для Many-to-Many (M2M)
class RolePermission(Base):
    __tablename__ = "RolePermissions"
    
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("Permissions.id", ondelete="CASCADE"), primary_key=True)


class Role(Base):
    __tablename__ = "Roles"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    role_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    
    # Связь M2M с Permission
    permissions: Mapped[List["Permission"]] = relationship(
        secondary="RolePermissions", back_populates="roles"
    )


class Permission(Base):
    __tablename__ = "Permissions"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    permission_name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    
    roles: Mapped[List["Role"]] = relationship(
        secondary="RolePermissions", back_populates="permissions"
    )


class Warehouse(Base):
    __tablename__ = "Warehouses"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str] = mapped_column(String, nullable=False)
    is_delete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class Employee(Base):
    __tablename__ = "Employees"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    # Полноценные связи для джоинов
    warehouse: Mapped["Warehouse"] = relationship()
    role: Mapped["Role"] = relationship()


class Product(Base):
    __tablename__ = "Products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    article_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    measurement_id: Mapped[int] = mapped_column(nullable=False)
    is_delete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class StockOnWarehouse(Base):
    __tablename__ = "StockOnWarehouse"
    
    # Исправлен регистр в ForeignKey
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("Products.id"), primary_key=True)
    
    # Decimal для Numeric типов данных
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    
    # ИСПРАВЛЕНО: функция вызывается при создании записи lambda: ...
    last_updated: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())


class Shipment(Base):
    __tablename__ = "Shipments"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    status_id: Mapped[int] = mapped_column(nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    creator_id: Mapped[int] = mapped_column(ForeignKey("Employees.id"), nullable=False)
    sender_client_id: Mapped[Optional[int]] = mapped_column(nullable=True)


class ShipmentStage(Base):
    __tablename__ = "ShipmentStages"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("Shipments.id"), nullable=False)
    stage_order: Mapped[int] = mapped_column(nullable=False)
    status_id: Mapped[int] = mapped_column(nullable=False)
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), nullable=False)
    acceptor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("Employees.id"), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class StageItem(Base):
    __tablename__ = "StageItems"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("ShipmentStages.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("Products.id"), nullable=False)
    document_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)

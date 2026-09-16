from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import ForeignKey, Numeric, DateTime, Date, String
from sqlalchemy.orm import Mapped, mapped_column
from warehouse.DAL.entities.Base import Base  # Импортируем общий Base


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
    
    # Исправлено: точность изменена с (12, 0) на (12, 3) для весового товара
    document_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    actual_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(String, nullable=True)


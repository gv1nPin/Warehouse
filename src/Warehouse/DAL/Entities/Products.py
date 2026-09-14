from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, ForeignKey, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from Warehouse.DAL.Entities.Base import Base  # Импортируем общий Base


class Product(Base):
    __tablename__ = "Products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    article_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    measurement_id: Mapped[int] = mapped_column(nullable=False)
    is_delete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class StockOnWarehouse(Base):
    __tablename__ = "StockOnWarehouse"
    
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("Products.id"), primary_key=True)
    
    # Использование точного типа Numeric (Decimal) для складских остатков
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    
    # Лямбда-функция гарантирует, что дата генерируется в момент сохранения строки, а не старта сервера
    last_updated: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date())

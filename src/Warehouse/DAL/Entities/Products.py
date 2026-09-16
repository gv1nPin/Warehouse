from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import String, Boolean, ForeignKey, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from Warehouse.DAL.Entities.Base import Base 

class Product(Base):
    __tablename__ = "Products"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    article_number: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    measurement_id: Mapped[int] = mapped_column(nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class StockOnWarehouse(Base):
    __tablename__ = "StockOnWarehouse"
    
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("Products.id"), primary_key=True)
    
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    reserved_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal("0.0"))
    
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

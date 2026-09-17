from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from warehouse.dal.entities.product import Product
from warehouse.dal.entities.warehouse import Warehouse

from .base import Base


class StockOnWarehouse(Base):
    """Остаток товара на складе (Inventory)."""

    __tablename__ = "StockOnWarehouse"
    __table_args__ = (
        CheckConstraint(
            "reserved_quantity <= quantity",
            name="ck_StockOnWarehouse_reserved_le_quantity",
        ),
    )

    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("Products.id"), primary_key=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0, server_default="0")
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), default=0, server_default="0"
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    warehouse: Mapped["Warehouse"] = relationship(back_populates="stock")
    product: Mapped["Product"] = relationship(back_populates="stock")

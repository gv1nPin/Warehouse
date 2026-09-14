from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Numeric, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Warehouse(Base):
    __tablename__ = "Warehouses"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    employees: Mapped[list["Employee"]] = relationship(back_populates="warehouse")
    stock: Mapped[list["StockOnWarehouse"]] = relationship(back_populates="warehouse")


class Employee(Base):
    __tablename__ = "Employees"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), index=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("Roles.id"), index=True)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    warehouse: Mapped["Warehouse"] = relationship(back_populates="employees")
    role: Mapped["Role"] = relationship(back_populates="employees")


class Product(Base):
    __tablename__ = "Products"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    article_number: Mapped[str] = mapped_column(Text, unique=True)
    product_name: Mapped[str] = mapped_column(Text)
    measurement_id: Mapped[int] = mapped_column(ForeignKey("Measurements.id"), index=True)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    measurement: Mapped["Measurement"] = relationship(back_populates="products")
    stock: Mapped[list["StockOnWarehouse"]] = relationship(back_populates="product")


class StockOnWarehouse(Base):
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

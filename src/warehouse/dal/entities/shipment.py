from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from warehouse.dal.entities.employee import Employee
    from warehouse.dal.entities.product import Product
    from warehouse.dal.entities.reference import Status
    from warehouse.dal.entities.warehouse import Warehouse


class Shipment(Base):
    __tablename__ = "Shipments"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    status_id: Mapped[int] = mapped_column(ForeignKey("Statuses.id"), index=True)
    planned_date: Mapped[date]
    creator_id: Mapped[int] = mapped_column(ForeignKey("Employees.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    status: Mapped["Status"] = relationship()
    creator: Mapped["Employee"] = relationship()
    stages: Mapped[list["ShipmentStage"]] = relationship(
        back_populates="shipment",
        order_by="ShipmentStage.stage_order",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ShipmentStage(Base):
    __tablename__ = "ShipmentStages"
    __table_args__ = (
        UniqueConstraint("shipment_id", "stage_order", name="uq_ShipmentStages_shipment_order"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("Shipments.id", ondelete="CASCADE"))
    stage_order: Mapped[int]
    status_id: Mapped[int] = mapped_column(ForeignKey("Statuses.id"), index=True)
    from_warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), index=True)
    to_warehouse_id: Mapped[int] = mapped_column(ForeignKey("Warehouses.id"), index=True)
    acceptor_id: Mapped[int | None] = mapped_column(ForeignKey("Employees.id"), index=True)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("Employees.id"), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    shipment: Mapped["Shipment"] = relationship(back_populates="stages")
    status: Mapped["Status"] = relationship()
    from_warehouse: Mapped["Warehouse"] = relationship(foreign_keys=[from_warehouse_id])
    to_warehouse: Mapped["Warehouse"] = relationship(foreign_keys=[to_warehouse_id])
    acceptor: Mapped["Employee | None"] = relationship(foreign_keys=[acceptor_id])
    driver: Mapped["Employee | None"] = relationship(foreign_keys=[driver_id])
    items: Mapped[list["StageItem"]] = relationship(
        back_populates="stage", cascade="all, delete-orphan", passive_deletes=True
    )


class StageItem(Base):
    __tablename__ = "StageItems"
    __table_args__ = (
        UniqueConstraint("stage_id", "product_id", name="uq_StageItems_stage_product"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    stage_id: Mapped[int] = mapped_column(ForeignKey("ShipmentStages.id", ondelete="CASCADE"))
    product_id: Mapped[int] = mapped_column(ForeignKey("Products.id"), index=True)
    document_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    comment: Mapped[str | None] = mapped_column(Text)

    stage: Mapped["ShipmentStage"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()


class StageDocument(Base):
    """Документ этапа. Файл хранит web-слой, здесь только его данные.

    Удаляется вместе с этапом (ON DELETE CASCADE), но файл на диске
    при этом остаётся: убирать его — забота web-слоя.
    """

    __tablename__ = "StageDocuments"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("ShipmentStages.id", ondelete="CASCADE"), index=True
    )
    file_name: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("Employees.id"), index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    uploader: Mapped["Employee"] = relationship()

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Identity, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Warehouse.DAL.Entities.Base import Base


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

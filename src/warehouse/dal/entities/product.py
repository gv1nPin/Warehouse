from sqlalchemy import ForeignKey, Identity, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from warehouse.dal.entities.stock import StockOnWarehouse
from warehouse.dal.entities.reference import Measurement

from .base import Base


class Product(Base):
    __tablename__ = "Products"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    article_number: Mapped[str] = mapped_column(Text, unique=True)
    product_name: Mapped[str] = mapped_column(Text)
    measurement_id: Mapped[int] = mapped_column(ForeignKey("Measurements.id"), index=True)
    is_deleted: Mapped[bool] = mapped_column(default=False, server_default=false())

    measurement: Mapped["Measurement"] = relationship(back_populates="products")
    stock: Mapped[list["StockOnWarehouse"]] = relationship(back_populates="product")

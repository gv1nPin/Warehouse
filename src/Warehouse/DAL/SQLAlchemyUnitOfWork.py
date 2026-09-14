from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean, 
    Numeric, Date, DateTime, ForeignKey, Table
)
from sqlalchemy.orm import declarative_base, relationship, Session

Base = declarative_base()

class Role(Base):
    __tablename__ = "Roles"
    id = Column(Integer, primary_key=True)
    role_name = Column(String, nullable=False, unique=True)
    permissions = relationship("Permission", secondary="RolePermissions", back_populates="roles")

class Permission(Base):
    __tablename__ = "Permissions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    permission_name = Column(String, nullable=False, unique=True)
    description = Column(String)
    roles = relationship("Role", secondary="RolePermissions", back_populates="permissions")

class RolePermission(Base):
    __tablename__ = "RolePermissions"
    role_id = Column(Integer, ForeignKey("Roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("Permissions.id", ondelete="CASCADE"), primary_key=True)

class Warehouse(Base):
    __tablename__ = "Warehouses"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    address = Column(String, nullable=False)
    is_delete = Column(Boolean, default=False, nullable=False)

class Employee(Base):
    __tablename__ = "Employees"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    warehouse_id = Column(Integer, ForeignKey("Warehouses.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("Roles.id"), nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    
    role = relationship("Role")

class StockOnWarehouse(Base):
    __tablename__ = "StockOnWarehouse"
    Warehouse_id = Column(Integer, ForeignKey("Warehouses.id"), primary_key=True)
    Product_id = Column(Integer, ForeignKey("Products.id"), primary_key=True)
    # Ошибка исправлена: изменено на Numeric(12, 3) для точного весового учета
    quantity = Column(Numeric(12, 3), default=0.0)
    reserved_quantity = Column(Numeric(12, 3), default=0.0)
    last_updated = Column(Date, nullable=False, default=datetime.now(timezone.utc).date)

class Shipment(Base):
    __tablename__ = "Shipments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    status_id = Column(Integer, nullable=False)
    planned_date = Column(Date, nullable=False)
    creator_id = Column(Integer, ForeignKey("Employees.id"), nullable=False)
    sender_client_id = Column(Integer, nullable=True)

class ShipmentStage(Base):
    __tablename__ = "ShipmentStages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    shipment_id = Column(Integer, ForeignKey("Shipments.id"), nullable=False)
    stage_order = Column(Integer, nullable=False)
    status_id = Column(Integer, nullable=False)
    from_warehouse_id = Column(Integer, ForeignKey("Warehouses.id"), nullable=False)
    to_warehouse_id = Column(Integer, ForeignKey("Warehouses.id"), nullable=False)
    acceptor_id = Column(Integer, ForeignKey("Employees.id"), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)

class StageItem(Base):
    __tablename__ = "StageItems"
    id = Column(Integer, primary_key=True, autoincrement=True)
    stage_id = Column(Integer, ForeignKey("ShipmentStages.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("Products.id"), nullable=False)
    # Точность 12, 3 для документального и фактического веса/количества
    document_quantity = Column(Numeric(12, 3), nullable=False)
    actual_quantity = Column(Numeric(12, 3), nullable=True)
    comment = Column(String, nullable=True)

class Product(Base):
    __tablename__ = "Products"
    id = Column(Integer, primary_key=True)
    article_number = Column(String, nullable=False, unique=True)
    product_name = Column(String, nullable=False)
    measurement_id = Column(Integer, nullable=False)
    is_delete = Column(Boolean, default=False, nullable=False)

class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session: Optional[Session] = None

    def __enter__(self):
        self.session = self.session_factory()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.session.rollback()  # Откатываем транзакцию при любой ошибке
        else:
            self.session.commit()    # Сохраняем, если всё прошло успешно
        self.session.close()

class TransitRepository:
    def __init__(self, uow: SQLAlchemyUnitOfWork):
        self.uow = uow

    def get_stage_by_id(self, stage_id: int) -> Optional[dict]:
        stage = self.uow.session.query(ShipmentStage).filter_by(id=stage_id).first()
        if not stage:
            return None
        return {
            "id": stage.id,
            "shipment_id": stage.shipment_id,
            "stage_order": stage.stage_order,
            "status_id": stage.status_id,
            "from_warehouse_id": stage.from_warehouse_id
        }

    def update_shipment_status(self, shipment_id: int, status_id: int) -> None:
        shipment = self.uow.session.query(Shipment).filter_by(id=shipment_id).first()
        if shipment:
            shipment.status_id = status_id

    def update_stage_status(self, stage_id: int, status_id: int) -> None:
        stage = self.uow.session.query(ShipmentStage).filter_by(id=stage_id).first()
        if stage:
            stage.status_id = status_id

    def add_item_to_stage(self, stage_id: int, product_id: int, document_quantity: float) -> None:
        item = StageItem(
            stage_id=stage_id,
            product_id=product_id,
            document_quantity=document_quantity
        )
        self.uow.session.add(item)


from src.Warehouse.BLL.Common import ShipmentStatus  # Используем ваш IntEnum

class ShipmentTransitCoordinator:
    """
    Координатор транзита. Берет на себя автоматический кросс-докинг 
    и связывание старого и нового плеча доставки в одной неделимой транзакции.
    """
    def __init__(self, uow: SQLAlchemyUnitOfWork, transit_repo: TransitRepository, dispatch_service):
        self.uow = uow
        self.transit_repo = transit_repo
        self.dispatch_service = dispatch_service  # Внедряем зависимость от сервиса отправки

    def move_to_next_stage(self, current_stage_id: int, next_stage_id: int, accepted_items: Dict[int, float]) -> None:
        with self.uow:
            next_stage = self.transit_repo.get_stage_by_id(next_stage_id)
            if not next_stage:
                raise Exception("Следующий этап транзита не найден.")
            
            # 1. Меняем статус всей накладной на 'На транзитном складе'
            self.transit_repo.update_shipment_status(next_stage["shipment_id"], status_id=ShipmentStatus.IN_TRANSIT_WH)
            
            has_items_to_forward = False
            
            # 2. Формируем состав товаров для следующего плеча
            for product_id, actual_qty in accepted_items.items():
                if actual_qty > 0:
                    self.transit_repo.add_item_to_stage(
                        stage_id=next_stage_id, 
                        product_id=product_id, 
                        document_quantity=actual_qty
                    )
                    has_items_to_forward = True
            
            # Переводим следующий этап в статус Черновика, чтобы его можно было зарезервировать
            self.transit_repo.update_stage_status(next_stage_id, status_id=ShipmentStatus.DRAFT)
            
            # 3. Делегируем резервирование сервису отправки (в рамках этой же транзакции сессии)
            if has_items_to_forward:
                self.dispatch_service.reserve_stage_items(next_stage_id)

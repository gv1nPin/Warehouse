"""Перевод моделей SQLAlchemy в DTO. Вызывать только внутри открытой сессии."""

from ..DTO import (
    EmployeeDTO,
    RouteDTO,
    ShipmentDTO,
    StageItemDTO,
    StockItemDTO,
    WarehouseDTO,
)
from src.Warehouse.DAL.Entities import Employee, Shipment, ShipmentStage, StageItem, StockOnWarehouse, Warehouse


def to_employee(e: Employee) -> EmployeeDTO:
    return EmployeeDTO(
        id=e.id,
        first_name=e.first_name,
        last_name=e.last_name,
        login=e.login,
        role_id=e.role_id,
        role_name=e.role.role_name,
        warehouse_id=e.warehouse_id,
        is_deleted=e.is_deleted,
    )


def to_warehouse(w: Warehouse) -> WarehouseDTO:
    return WarehouseDTO(id=w.id, title=w.title, address=w.address)


def to_stock_item(s: StockOnWarehouse) -> StockItemDTO:
    return StockItemDTO(
        warehouse_id=s.warehouse_id,
        product_id=s.product_id,
        article_number=s.product.article_number,
        product_name=s.product.product_name,
        measurement_name=s.product.measurement.measurement_name,
        quantity=s.quantity,
        reserved_quantity=s.reserved_quantity,
    )


def to_stage_item(i: StageItem) -> StageItemDTO:
    return StageItemDTO(
        id=i.id,
        product_id=i.product_id,
        article_number=i.product.article_number,
        product_name=i.product.product_name,
        measurement_name=i.product.measurement.measurement_name,
        document_quantity=i.document_quantity,
        actual_quantity=i.actual_quantity,
        comment=i.comment,
    )


def to_route(st: ShipmentStage, with_items: bool = False) -> RouteDTO:
    return RouteDTO(
        stage_id=st.id,
        shipment_id=st.shipment_id,
        stage_order=st.stage_order,
        status_name=st.status.status_name,
        shipment_status_name=st.shipment.status.status_name,
        planned_date=st.shipment.planned_date,
        creator_id=st.shipment.creator_id,
        from_warehouse=to_warehouse(st.from_warehouse),
        to_warehouse=to_warehouse(st.to_warehouse),
        driver_id=st.driver_id,
        driver_name=f"{st.driver.last_name} {st.driver.first_name}" if st.driver else None,
        acceptor_id=st.acceptor_id,
        sent_at=st.sent_at,
        received_at=st.received_at,
        items=tuple(to_stage_item(i) for i in st.items) if with_items else (),
    )


def to_shipment(sh: Shipment) -> ShipmentDTO:
    return ShipmentDTO(
        id=sh.id,
        status_name=sh.status.status_name,
        planned_date=sh.planned_date,
        created_at=sh.created_at,
        creator_id=sh.creator_id,
        creator_name=f"{sh.creator.last_name} {sh.creator.first_name}",
        stages=tuple(to_route(st, with_items=True) for st in sh.stages),
    )

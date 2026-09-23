from warehouse.common.dto import ShipmentDTO, StageDTO, StageItemDTO
from warehouse.dal.entities import Shipment, ShipmentStage, StageItem
from .warehouse import to_warehouse


def to_stage_item(i: StageItem) -> StageItemDTO:
    return StageItemDTO(
        id=i.id,
        stage_id=i.stage_id,
        product_id=i.product_id,
        article_number=i.product.article_number,
        product_name=i.product.product_name,
        measurement_name=i.product.measurement.measurement_name,
        document_quantity=i.document_quantity,
        actual_quantity=i.actual_quantity,
        comment=i.comment,
    )


def to_stage(st: ShipmentStage, with_items: bool = False) -> StageDTO:
    return StageDTO(
        id=st.id,
        shipment_id=st.shipment_id,
        stage_order=st.stage_order,
        status_id=st.status_id,
        status_name=st.status.status_name,
        shipment_status_id=st.shipment.status_id,
        shipment_status_name=st.shipment.status.status_name,
        planned_date=st.shipment.planned_date,
        creator_id=st.shipment.creator_id,
        from_warehouse=to_warehouse(st.from_warehouse),
        to_warehouse=to_warehouse(st.to_warehouse),
        driver_id=st.driver_id,
        driver_name=st.driver.full_name if st.driver else None,
        acceptor_id=st.acceptor_id,
        sent_at=st.sent_at,
        received_at=st.received_at,
        items=tuple(to_stage_item(i) for i in st.items) if with_items else (),
    )


def to_shipment(sh: Shipment) -> ShipmentDTO:
    return ShipmentDTO(
        id=sh.id,
        status_id=sh.status_id,
        status_name=sh.status.status_name,
        planned_date=sh.planned_date,
        created_at=sh.created_at,
        creator_id=sh.creator_id,
        creator_name=sh.creator.full_name,
        stages=tuple(to_stage(st, with_items=True) for st in sh.stages),
    )

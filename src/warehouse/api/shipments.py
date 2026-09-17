from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from dependency_injector.wiring import inject, Provide

from container import Container
from warehouse.api.dependencies import PermissionChecker
from warehouse.api.schemas.shipments_dto import (
    ShipmentDraftCreateInputDTO, 
    ItemToStageAddInputDTO, 
    ActualQuantityInputDTO,
    IncomingStageOutputDTO,
    BaseActionResponseDTO
)
from warehouse.bll.services.shipment_service.shipment_dispatch_service import ShipmentDispatchService
from warehouse.bll.services.shipment_service.shipment_receipt_service import ShipmentReceiptService
from warehouse.api.mappers.shipments_mappers import ShipmentMapper  # Внедряем маппер

router = APIRouter(prefix="/shipments", tags=["Warehouse Shipments"])

@router.post("/draft", status_code=status.HTTP_201_CREATED)
@inject
def create_draft(
    payload: ShipmentDraftCreateInputDTO,
    current_user: dict = Depends(PermissionChecker("shipment:create")),
    dispatch_service: ShipmentDispatchService = Depends(Provide[Container.dispatch_service])
):
    try:
        creator_id = int(current_user["sub"])
        shipment_id = dispatch_service.create_shipment_draft(
            creator_id=creator_id,
            planned_date=payload.planned_date,
            route_warehouses=payload.route_warehouses
        )
        return {"status": "success", "shipment_id": shipment_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/items", response_model=BaseActionResponseDTO)
@inject
def add_item_to_stage(
    payload: ItemToStageAddInputDTO,
    current_user: dict = Depends(PermissionChecker("shipment:create")),
    dispatch_service: ShipmentDispatchService = Depends(Provide[Container.dispatch_service])
):
    try:
        dispatch_service.add_item_to_stage(
            stage_id=payload.stage_id,
            product_id=payload.product_id,
            document_quantity=float(payload.document_quantity)
        )
        return BaseActionResponseDTO(message="Товар успешно добавлен в этап.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reserve/{stage_id}", response_model=BaseActionResponseDTO)
@inject
def reserve_items(
    stage_id: int,
    current_user: dict = Depends(PermissionChecker("shipment:create")),
    dispatch_service: ShipmentDispatchService = Depends(Provide[Container.dispatch_service])
):
    try:
        dispatch_service.reserve_stage_items(stage_id=stage_id)
        return BaseActionResponseDTO(message="Товары успешно зарезервированы на складе.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/ship/{stage_id}", response_model=BaseActionResponseDTO)
@inject
def ship_stage(
    stage_id: int,
    current_user: dict = Depends(PermissionChecker("shipment:create")),
    dispatch_service: ShipmentDispatchService = Depends(Provide[Container.dispatch_service])
):
    try:
        dispatch_service.ship_stage(stage_id=stage_id)
        return BaseActionResponseDTO(message="Груз успешно отправлен со склада.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/incoming/{warehouse_id}", response_model=List[IncomingStageOutputDTO])
@inject
def get_incoming_stages(
    warehouse_id: int,
    current_user: dict = Depends(PermissionChecker("shipment:accept")),
    receipt_service: ShipmentReceiptService = Depends(Provide[Container.receipt_service])
):
    # Извлекаем сырые данные/структуры из слоя BLL
    raw_incoming_stages = receipt_service.get_incoming_stages(warehouse_id=warehouse_id)
    
    # МАППИНГ: Быстрая и предсказуемая трансформация в список выходных DTO
    return ShipmentMapper.to_incoming_stage_dto_list(raw_incoming_stages)

@router.post("/stages/{stage_id}/products/{product_id}/actual-quantity", response_model=BaseActionResponseDTO)
@inject
def enter_actual_quantity(
    stage_id: int,
    product_id: int,
    payload: ActualQuantityInputDTO,
    current_user: dict = Depends(PermissionChecker("shipment:accept")),
    receipt_service: ShipmentReceiptService = Depends(Provide[Container.receipt_service])
):
    try:
        receipt_service.enter_actual_quantity(
            stage_id=stage_id,
            product_id=product_id,
            actual_quantity=float(payload.actual_quantity)
        )
        return BaseActionResponseDTO(message="Фактическое количество успешно зафиксировано.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/accept/{stage_id}", response_model=BaseActionResponseDTO)
@inject
def accept_stage(
    stage_id: int,
    current_user: dict = Depends(PermissionChecker("shipment:accept")),
    receipt_service: ShipmentReceiptService = Depends(Provide[Container.receipt_service])
):
    try:
        employee_id = int(current_user["sub"])
        receipt_service.accept_stage(stage_id=stage_id, employee_id=employee_id)
        return BaseActionResponseDTO(message="Этап перевозки успешно принят на складе назначения.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

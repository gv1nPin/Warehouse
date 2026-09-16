# src/Warehouse/API/Mappers/Shipments_mappers.py
from typing import List, Dict, Any
from Warehouse.API.Schemas.Shipments_dto import IncomingStageOutputDTO

class ShipmentMapper:
    @staticmethod
    def to_incoming_stage_dto(stage_data: Dict[str, Any]) -> IncomingStageOutputDTO:
        """Трансформирует данные этапа из формата BLL/DAL в интерфейсный DTO."""
        return IncomingStageOutputDTO(
            stage_id=stage_data["stage_id"],
            shipment_id=stage_data["shipment_id"],
            stage_order=stage_data["stage_order"],
            planned_date=stage_data["planned_date"],
            sent_at=stage_data["sent_at"]
        )

    @staticmethod
    def to_incoming_stage_dto_list(stages_list: List[Dict[str, Any]]) -> List[IncomingStageOutputDTO]:
        """Трансформирует массив данных в массив DTO."""
        return [ShipmentMapper.to_incoming_stage_dto(stage) for stage in stages_list]

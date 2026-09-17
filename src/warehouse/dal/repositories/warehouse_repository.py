from sqlalchemy import select

from warehouse.api.dto import WarehouseDTO
from ..entities import Warehouse
from warehouse.api.mappers import to_warehouse
from .base_repository import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    model = Warehouse

    def get_by_id(self, warehouse_id: int) -> WarehouseDTO | None:
        w = self._get(warehouse_id)
        return to_warehouse(w) if w and not w.is_deleted else None

    def list_active(self) -> list[WarehouseDTO]:
        stmt = select(Warehouse).where(Warehouse.is_deleted.is_(False)).order_by(Warehouse.title)
        return [to_warehouse(w) for w in self._all(stmt)]

    def create(self, title: str, address: str) -> int:
        return self._add(Warehouse(title=title, address=address)).id

    def soft_delete(self, warehouse_id: int) -> bool:
        return self._update(warehouse_id, is_deleted=True)

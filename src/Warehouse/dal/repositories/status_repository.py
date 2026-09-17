from sqlalchemy import select

from Warehouse.dal.entities import Status
from .base_repository import BaseRepository


class StatusRepository(BaseRepository[Status]):
    """Справочник статусов. id в БД не 1, 2, 3..., поэтому статус всегда ищем по имени."""

    model = Status

    def get_id(self, status_name: str) -> int | None:
        return self.session.scalar(select(Status.id).where(Status.status_name == status_name))

    def get_name(self, status_id: int) -> str | None:
        return self.session.scalar(select(Status.status_name).where(Status.id == status_id))

    def list_all(self) -> dict[int, str]:
        """{id: название}."""
        stmt = select(Status.id, Status.status_name)
        return dict(self.session.execute(stmt).tuples().all())

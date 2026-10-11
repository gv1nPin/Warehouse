from sqlalchemy import select

from warehouse.common.exceptions import NotFoundError
from warehouse.dal.entities import Status
from .base_repository import BaseRepository


class StatusRepository(BaseRepository[Status]):
    """Справочник статусов. id в БД не 1, 2, 3..., поэтому статус всегда ищем по имени."""

    model = Status

    def get_id(self, status_name: str) -> int | None:
        return self.session.scalar(select(Status.id).where(Status.status_name == status_name))

    def require_id(self, status_name: str) -> int:
        """id статуса по имени; нет в справочнике -> NotFoundError."""
        status_id = self.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

    def get_name(self, status_id: int) -> str | None:
        return self.session.scalar(select(Status.status_name).where(Status.id == status_id))

    def list_all(self) -> dict[int, str]:
        """{id: название}."""
        stmt = select(Status.id, Status.status_name)
        return dict(self.session.execute(stmt).tuples().all())

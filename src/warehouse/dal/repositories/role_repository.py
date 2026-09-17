from sqlalchemy import select

from ..entities import Role
from .base_repository import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Справочник ролей."""

    model = Role

    def get_id(self, role_name: str) -> int | None:
        return self.session.scalar(select(Role.id).where(Role.role_name == role_name))

    def get_name(self, role_id: int) -> str | None:
        return self.session.scalar(select(Role.role_name).where(Role.id == role_id))

    def list_all(self) -> dict[int, str]:
        """{id: название}."""
        return dict(self.session.execute(select(Role.id, Role.role_name)).tuples().all())

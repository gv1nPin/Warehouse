from sqlalchemy import select
from sqlalchemy.orm import Session

from Warehouse.DAL.Entities.references import Measurement, Role, Status


class ReferenceRepository:
    """Справочники: роли, статусы, единицы измерения."""

    def __init__(self, session: Session):
        self.session = session

    def get_status_id(self, status_name: str) -> int | None:
        return self.session.scalar(select(Status.id).where(Status.status_name == status_name))

    def get_role_id(self, role_name: str) -> int | None:
        return self.session.scalar(select(Role.id).where(Role.role_name == role_name))

    def list_statuses(self) -> dict[int, str]:
        return dict(self.session.execute(select(Status.id, Status.status_name)).tuples().all())

    def list_roles(self) -> dict[int, str]:
        return dict(self.session.execute(select(Role.id, Role.role_name)).tuples().all())

    def list_measurements(self) -> dict[int, str]:
        rows = select(Measurement.id, Measurement.measurement_name)
        return dict(self.session.execute(rows).tuples().all())

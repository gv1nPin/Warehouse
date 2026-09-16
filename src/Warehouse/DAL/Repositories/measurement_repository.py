from sqlalchemy import select

from ..Entities import Measurement
from .base_repository import BaseRepository


class MeasurementRepository(BaseRepository[Measurement]):
    """Справочник единиц измерения."""

    model = Measurement

    def list_all(self) -> dict[int, str]:
        """{id: название}."""
        stmt = select(Measurement.id, Measurement.measurement_name)
        return dict(self.session.execute(stmt).tuples().all())

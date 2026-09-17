from typing import Any, Generic, TypeVar

from sqlalchemy import Select, delete, update
from sqlalchemy.orm import Session

from Warehouse.dal.entities import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Общая основа всех репозиториев.

    Наследник указывает свою сущность:

        class WarehouseRepository(BaseRepository[Warehouse]):
            model = Warehouse

    Методы с "_" возвращают модели SQLAlchemy и нужны только внутри репозиториев.
    Наружу (в BLL) репозиторий всегда отдаёт DTO.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    # Все чтения сущностей идут через _get/_one/_all с populate_existing:
    # иначе после update() в той же транзакции сессия вернёт старые данные из кэша.

    def _get(self, entity_id: Any) -> ModelT | None:
        return self.session.get(self.model, entity_id, populate_existing=True)

    def _one(self, stmt: Select) -> Any:
        return self.session.scalar(stmt.execution_options(populate_existing=True))

    def _all(self, stmt: Select) -> list[Any]:
        return list(self.session.scalars(stmt.execution_options(populate_existing=True)))

    def _add(self, entity: ModelT) -> ModelT:
        """Добавляет запись и сразу получает её id от БД (без commit)."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def _update(self, entity_id: int, **values: Any) -> bool:
        result = self.session.execute(
            update(self.model).where(self.model.id == entity_id).values(**values)
        )
        return result.rowcount > 0

    def _delete(self, entity_id: int) -> bool:
        result = self.session.execute(delete(self.model).where(self.model.id == entity_id))
        return result.rowcount > 0

from collections.abc import Callable, Collection

from warehouse.common.dto import ShipmentDTO, StageDTO
from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.bll.interfaces.shipment_service.abstract_route_query_service import (
    AbstractRouteQueryService,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import AccessDeniedError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork

# Маршрут ещё в работе: его пока не приняли.
ACTIVE_STATUSES = (
    StatusName.DRAFT,
    StatusName.WAITING,
    StatusName.RESERVED,
    StatusName.SHIPPED,
)

# Кто видит все маршруты своего склада, а не только свои рейсы.
WAREHOUSE_PERMISSIONS = frozenset(
    {PermissionName.SHIPMENT_CREATE, PermissionName.SHIPMENT_ACCEPT}
)


class RouteQueryService(AbstractRouteQueryService):
    """Просмотр маршрутов. Права проверяем от самых широких к самым узким:

    employee:manage                   — все маршруты;
    shipment:create / shipment:accept — маршруты своего склада;
    остальные                         — только рейсы, где сотрудник водитель или приёмщик.
    """

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    def list_routes(self, employee_id: int, only_active: bool = False) -> list[StageDTO]:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)
            status_ids = self._status_ids(uow, ACTIVE_STATUSES) if only_active else None

            if self._access.is_admin(actor):
                return uow.stages.list_all(status_ids=status_ids)

            if self._sees_whole_warehouse(actor):
                return uow.stages.list_for_warehouse(
                    warehouse_id=actor.employee.warehouse_id,
                    status_ids=status_ids,
                )

            # Ни прав склада, ни админских: сотрудник видит только свои рейсы.
            # Их может не быть — это пустой список, а не отказ в доступе.
            return uow.stages.list_for_driver(
                driver_id=actor.employee.id,
                status_ids=status_ids,
            )

    def get_route(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)

            stage = uow.stages.get_by_id(stage_id, with_items=True)
            if stage is None:
                raise NotFoundError(f"Маршрут №{stage_id} не найден")

            if not self._can_view_stage(actor, stage):
                raise AccessDeniedError("Нет прав на просмотр этого маршрута")

            return stage

    def get_shipment_progress(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)

            shipment = uow.shipments.get_by_id(shipment_id)
            if shipment is None:
                raise NotFoundError(f"Перевозка №{shipment_id} не найдена")

            # Перевозку видно, если виден хотя бы один её этап.
            if not any(self._can_view_stage(actor, stage) for stage in shipment.stages):
                raise AccessDeniedError("Нет прав на просмотр этой перевозки")

            return shipment

    def _can_view_stage(self, actor: ActorDTO, stage: StageDTO) -> bool:
        if self._access.is_admin(actor):
            return True

        if self._sees_whole_warehouse(actor) and actor.employee.warehouse_id in (
            stage.from_warehouse.id,
            stage.to_warehouse.id,
        ):
            return True

        return actor.employee.id in (stage.driver_id, stage.acceptor_id)

    @staticmethod
    def _sees_whole_warehouse(actor: ActorDTO) -> bool:
        return bool(actor.permissions & WAREHOUSE_PERMISSIONS)

    @staticmethod
    def _status_ids(uow: UnitOfWork, names: Collection[StatusName]) -> list[int]:
        """id статусов по именам. Неизвестные имена молча пропускаем:
        это фильтр, а не действие, и падать из-за него не нужно."""
        ids = (uow.statuses.get_id(name) for name in names)
        return [status_id for status_id in ids if status_id is not None]

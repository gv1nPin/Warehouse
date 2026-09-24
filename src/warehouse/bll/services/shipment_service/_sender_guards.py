import logging
from collections.abc import Collection

from warehouse.common.dto import StageDTO
from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import InvalidStatusError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork


class SenderGuardsMixin:
    """Общие проверки «кто -> куда -> что» для сервисов склада-отправителя.

    ShipmentDraftService и ShipmentDispatchService работают со складом
    отправления (from_warehouse), поэтому проверки для них общие и вынесены
    сюда, а не продублированы в двух файлах. Право у них разное:
    черновик — SHIPMENT_CREATE, резерв и отправка — SHIPMENT_DISPATCH.

    Класс-потребитель обязан завести self._access: AbstractAccessService
    и указать _permission — право, без которого в сервис не пускаем.
    """

    _access: AbstractAccessService
    _permission: PermissionName

    def _sender(self, uow: UnitOfWork, employee_id: int) -> ActorDTO:
        """Сотрудник с правом этого сервиса. Нет права -> AccessDeniedError."""
        actor = self._access.get_actor(uow, employee_id)
        self._access.require_permission(actor, self._permission)
        return actor

    def _stage_from_my_warehouse(
        self, uow: UnitOfWork, actor: ActorDTO, stage_id: int
    ) -> StageDTO:
        """Этап, который уходит со склада сотрудника. Чужой склад -> AccessDeniedError."""
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")

        # ФИКС: Проверяем склад и логируем варнинг ТОЛЬКО если пользователь не админ
        if not self._access.is_admin(actor):
            if actor.employee.warehouse_id != stage.from_warehouse.id:
                logging.warning(
                    "Попытка несанкционированного доступа: сотрудник №%s (склад №%s) "
                    "обратился к этапу №%s со склада №%s",
                    actor.employee.id,
                    actor.employee.warehouse_id,
                    stage.id,
                    stage.from_warehouse.id,
                )
                
        self._access.require_warehouse(actor, stage.from_warehouse.id)
        return stage


    def _editable_stage(self, uow: UnitOfWork, actor: ActorDTO, stage_id: int) -> StageDTO:
        """Первый этап в статусе «Черновик» — только его товары правят руками."""
        stage = self._stage_from_my_warehouse(uow, actor, stage_id)
        if stage.stage_order != 1:
            raise InvalidStatusError(
                "Товары этого этапа заполняются автоматически после приёмки предыдущего"
            )
        self._require_status(uow, stage, StatusName.DRAFT)
        return stage

    def _require_status(self, uow: UnitOfWork, stage: StageDTO, status: StatusName) -> None:
        if stage.status_id != self._status_id(uow, status):
            raise InvalidStatusError(
                f"Этап в статусе «{stage.status_name}»: действие доступно "
                f"только в статусе «{status}»"
            )

    @staticmethod
    def _status_id(uow: UnitOfWork, status_name: StatusName) -> int:
        status_id = uow.statuses.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

    @staticmethod
    def _status_ids(uow: UnitOfWork, names: Collection[StatusName]) -> list[int]:
        ids = (uow.statuses.get_id(name) for name in names)
        return [status_id for status_id in ids if status_id is not None]

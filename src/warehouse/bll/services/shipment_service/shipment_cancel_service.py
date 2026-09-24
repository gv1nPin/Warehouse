import logging
from collections.abc import Callable, Collection

from warehouse.common.dto import ShipmentDTO, StageDTO
from warehouse.bll.interfaces.auth_service import AbstractAccessService
from warehouse.bll.interfaces.shipment_service.abstract_shipment_cancel_service import (
    AbstractShipmentCancelService,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import InvalidStatusError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork

# Пока все этапы в этих статусах, груз ещё не уехал со склада — отменять можно.
CANCELLABLE_STATUSES = (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)


class ShipmentCancelService(AbstractShipmentCancelService):
    """Отмена перевозки: право SHIPMENT_CANCEL (менеджер, администратор).

    К складу не привязан: менеджер отменяет перевозки любого склада.
    Отменить можно, только пока ни один этап не отправлен: груз в пути
    отменой не вернуть, его нужно принять.

    В отличие от delete_draft, запись не удаляется, а получает статус
    «Отменено»: резерв на складе был реальным действием, история нужна.

    Транзакцию открывает сам, поэтому вызывается прямо из web.
    """

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    def cancel_shipment(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)
            self._access.require_permission(actor, PermissionName.SHIPMENT_CANCEL)

            shipment = self._shipment(uow, shipment_id)

            cancellable = self._status_ids(uow, CANCELLABLE_STATUSES)
            if shipment.status_id not in cancellable or any(
                stage.status_id not in cancellable for stage in shipment.stages
            ):
                raise InvalidStatusError(
                    f"Перевозка в статусе «{shipment.status_name}»: отменить можно, "
                    f"пока груз не отправлен"
                )

            reserved_id = self._status_id(uow, StatusName.RESERVED)
            for stage in shipment.stages:
                if stage.status_id == reserved_id:
                    self._release_reserve(uow, stage)

            cancelled_id = self._status_id(uow, StatusName.CANCELLED)
            for stage in shipment.stages:
                uow.stages.set_status(stage.id, cancelled_id)
            uow.shipments.set_status(shipment_id, cancelled_id)

            logging.info(
                "Сотрудник №%s отменил перевозку №%s", actor.employee.id, shipment_id
            )
            return self._shipment(uow, shipment_id)

    @staticmethod
    def _release_reserve(uow: UnitOfWork, stage: StageDTO) -> None:
        """Возвращает товар этапа в свободный остаток склада отправления."""
        warehouse_id = stage.from_warehouse.id
        # for_update по той же причине, что и в резерве: не даём двум операциям
        # одновременно менять один и тот же остаток.
        stock = uow.stock.get_many(
            warehouse_id, (item.product_id for item in stage.items), for_update=True
        )
        for item in stage.items:
            row = stock.get(item.product_id)
            # Резерв ставила система, так что расхождение здесь — сбой данных.
            if row is None or row.reserved_quantity < item.document_quantity:
                raise InvalidStatusError(
                    f"Резерв товара «{item.product_name}» на складе №{warehouse_id} "
                    f"не найден, отменить перевозку нельзя"
                )
            uow.stock.change(
                warehouse_id=warehouse_id,
                product_id=item.product_id,
                reserved_delta=-item.document_quantity,
            )

    @staticmethod
    def _shipment(uow: UnitOfWork, shipment_id: int) -> ShipmentDTO:
        shipment = uow.shipments.get_by_id(shipment_id)
        if shipment is None:
            raise NotFoundError(f"Перевозка №{shipment_id} не найдена")
        return shipment

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

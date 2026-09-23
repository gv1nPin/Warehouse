import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal

from warehouse.api.dto import StageDTO
from warehouse.bll.interfaces.auth_service import AbstractAccessService
from warehouse.bll.interfaces.shipment_service.abstract_shipment_dispatch_service import (
    AbstractShipmentDispatchService,
)
from warehouse.common import StatusName
from warehouse.common.exceptions import InvalidStatusError, NotFoundError, ValidationError
from warehouse.dal.unit_of_work import UnitOfWork

from ._sender_guards import SenderGuardsMixin


class ShipmentDispatchService(SenderGuardsMixin, AbstractShipmentDispatchService):
    """Диспетчеризация: резерв и отправка уже готового этапа со склада сотрудника.

    Черновик (маршрут, товары, водитель) собирает ShipmentDraftService —
    этот сервис его не редактирует, только резервирует остаток под готовый
    этап и списывает его при отправке.

    Проверяем в порядке «кто → куда → что», как и в приёмке.
    Транзакцию открывает сам, поэтому вызывается прямо из web.
    """

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    def reserve_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._editable_stage(uow, actor, stage_id)

            if not stage.items:
                raise ValidationError("В этапе нет ни одной позиции")

            warehouse_id = stage.from_warehouse.id
            # for_update блокирует строки до конца транзакции, чтобы двое
            # не зарезервировали один и тот же товар одновременно.
            stock = uow.stock.get_many(
                warehouse_id, (item.product_id for item in stage.items), for_update=True
            )
            for item in stage.items:
                row = stock.get(item.product_id)
                available = row.available if row is not None else Decimal(0)
                if available < item.document_quantity:
                    raise InvalidStatusError(
                        f"На складе свободно {available} {item.measurement_name} "
                        f"товара «{item.product_name}», а нужно {item.document_quantity}"
                    )
                uow.stock.change(
                    warehouse_id=warehouse_id,
                    product_id=item.product_id,
                    reserved_delta=item.document_quantity,
                )

            reserved_id = self._status_id(uow, StatusName.RESERVED)
            uow.stages.set_status(stage_id, reserved_id)
            uow.shipments.set_status(stage.shipment_id, reserved_id)

            logging.info(
                "Сотрудник №%s зарезервировал этап №%s на складе №%s",
                actor.employee.id,
                stage_id,
                warehouse_id,
            )
            return self._stage(uow, stage_id)

    def ship_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._stage_from_my_warehouse(uow, actor, stage_id)
            self._require_status(uow, stage, StatusName.RESERVED)

            if not stage.items:
                raise ValidationError("В этапе нет ни одной позиции")

            warehouse_id = stage.from_warehouse.id
            stock = uow.stock.get_many(
                warehouse_id, (item.product_id for item in stage.items), for_update=True
            )
            for item in stage.items:
                row = stock.get(item.product_id)
                # Резерв делали мы же, так что расхождение здесь — сбой данных,
                # а не ошибка пользователя. Отказываем, пока CHECK в БД не уронил коммит.
                if row is None or row.reserved_quantity < item.document_quantity:
                    raise InvalidStatusError(
                        f"Резерв товара «{item.product_name}» на складе не найден, "
                        f"отправка невозможна"
                    )
                uow.stock.change(
                    warehouse_id=warehouse_id,
                    product_id=item.product_id,
                    quantity_delta=-item.document_quantity,
                    reserved_delta=-item.document_quantity,
                )

            shipped_id = self._status_id(uow, StatusName.SHIPPED)
            uow.stages.set_status(stage_id, shipped_id, sent_at=datetime.now(timezone.utc))
            uow.shipments.set_status(stage.shipment_id, shipped_id)

            logging.info(
                "Сотрудник №%s отправил этап №%s со склада №%s на склад №%s",
                actor.employee.id,
                stage_id,
                warehouse_id,
                stage.to_warehouse.id,
            )
            return self._stage(uow, stage_id)

    def cancel_reservation(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._sender(uow, employee_id)
            stage = self._stage_from_my_warehouse(uow, actor, stage_id)
            self._require_status(uow, stage, StatusName.RESERVED)

            warehouse_id = stage.from_warehouse.id
            # for_update по той же причине, что и в reserve_stage/ship_stage:
            # не даём двум операциям одновременно менять один и тот же резерв.
            stock = uow.stock.get_many(
                warehouse_id, (item.product_id for item in stage.items), for_update=True
            )
            for item in stage.items:
                row = stock.get(item.product_id)
                # Резерв делали мы же, так что расхождение здесь — сбой данных.
                if row is None or row.reserved_quantity < item.document_quantity:
                    raise InvalidStatusError(
                        f"Резерв товара «{item.product_name}» на складе не найден, "
                        f"отменить нечего"
                    )
                uow.stock.change(
                    warehouse_id=warehouse_id,
                    product_id=item.product_id,
                    reserved_delta=-item.document_quantity,
                )

            cancelled_id = self._status_id(uow, StatusName.CANCELLED)
            uow.stages.set_status(stage_id, cancelled_id)
            uow.shipments.set_status(stage.shipment_id, cancelled_id)

            logging.info(
                "Сотрудник №%s отменил резерв этапа №%s на складе №%s",
                actor.employee.id,
                stage_id,
                warehouse_id,
            )
            return self._stage(uow, stage_id)

    @staticmethod
    def _stage(uow: UnitOfWork, stage_id: int) -> StageDTO:
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")
        return stage

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from warehouse.common.dto import StageDTO, StageItemDTO
from warehouse.bll.interfaces.auth_service import AbstractAccessService, ActorDTO
from warehouse.bll.interfaces.shipment_service.abstract_shipment_receipt_service import (
    AbstractShipmentReceiptService,
)
from warehouse.bll.interfaces.shipment_service.abstract_shipment_transit_coordinator import (
    AbstractShipmentTransitCoordinator,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import (
    InvalidStatusError,
    NotFoundError,
    ValidationError,
)
from warehouse.dal.unit_of_work import UnitOfWork


class ShipmentReceiptService(AbstractShipmentReceiptService):
    """Приёмка груза на складе назначения.

    Принимать можно только этап в статусе «Отправлено» и только на своём складе.
    Проверяем в порядке «кто → куда → что»: сначала право приёмки, потом свой ли
    это склад, и только потом статус этапа — чтобы по тексту ошибки нельзя было
    узнать, что происходит с грузом на чужом складе.

    Транзакцию открывает сам, поэтому вызывается прямо из web.
    """

    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        access: AbstractAccessService,
        transit: AbstractShipmentTransitCoordinator,
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access
        self._transit = transit

    def get_incoming(self, employee_id: int) -> list[StageDTO]:
        with self._uow_factory() as uow:
            actor = self._receiver(uow, employee_id)
            return uow.stages.list_incoming(
                warehouse_id=actor.employee.warehouse_id,
                status_ids=[self._status_id(uow, StatusName.SHIPPED)],
                with_items=True,
            )

    def enter_actual_quantity(
        self,
        employee_id: int,
        item_id: int,
        quantity: Decimal,
        comment: str | None = None,
    ) -> None:
        quantity = self._to_quantity(quantity)

        with self._uow_factory() as uow:
            actor = self._receiver(uow, employee_id)

            item = uow.stage_items.get_by_id(item_id)
            if item is None:
                raise NotFoundError(f"Позиция №{item_id} не найдена")

            stage = self._stage_on_my_warehouse(uow, actor, item.stage_id)
            self._require_shipped(uow, stage)

            comment = (comment or "").strip() or None
            if quantity != item.document_quantity and comment is None:
                raise ValidationError("Факт расходится с документом — заполните комментарий")

            uow.stage_items.set_actual_quantity(item_id, quantity, comment)

    def check_discrepancies(self, employee_id: int, stage_id: int) -> list[StageItemDTO]:
        with self._uow_factory() as uow:
            actor = self._receiver(uow, employee_id)
            stage = self._stage_on_my_warehouse(uow, actor, stage_id)

            return [item for item in stage.items if self._is_discrepancy(item)]

    def accept_stage(self, employee_id: int, stage_id: int) -> StageDTO:
        with self._uow_factory() as uow:
            actor = self._receiver(uow, employee_id)
            stage = self._stage_on_my_warehouse(uow, actor, stage_id)
            self._require_shipped(uow, stage)

            if not stage.items:
                raise ValidationError("В этапе нет ни одной позиции")
            if any(item.actual_quantity is None for item in stage.items):
                raise ValidationError("Заполните факт по всем позициям перед приёмкой")

            has_discrepancies = any(self._is_discrepancy(item) for item in stage.items)
            final_status = StatusName.DISCREPANCY if has_discrepancies else StatusName.RECEIVED

            # Финальный статус ставим до транзита: координатор по статусам
            # этапов решает, чем закончилась вся перевозка.
            uow.stages.set_status(
                stage_id,
                self._status_id(uow, final_status),
                received_at=datetime.now(timezone.utc),
                acceptor_id=actor.employee.id,
            )

            # Факт приходуем тоже до транзита: следующий этап
            # резервируется из этого же остатка.
            for item in stage.items:
                if item.actual_quantity > 0:
                    uow.stock.add_quantity(
                        warehouse_id=stage.to_warehouse.id,
                        product_id=item.product_id,
                        amount=item.actual_quantity,
                    )

            self._transit.after_stage_accepted(uow, stage_id)

            logging.info(
                "Сотрудник №%s принял этап №%s на складе №%s со статусом «%s»",
                actor.employee.id,
                stage_id,
                stage.to_warehouse.id,
                final_status,
            )

            accepted = uow.stages.get_by_id(stage_id, with_items=True)
            if accepted is None:
                raise NotFoundError(f"Этап №{stage_id} не найден")
            return accepted

    def _receiver(self, uow: UnitOfWork, employee_id: int) -> ActorDTO:
        """Сотрудник с правом приёмки. Нет права -> AccessDeniedError."""
        actor = self._access.get_actor(uow, employee_id)
        self._access.require_permission(actor, PermissionName.SHIPMENT_ACCEPT)
        return actor

    def _stage_on_my_warehouse(
        self, uow: UnitOfWork, actor: ActorDTO, stage_id: int
    ) -> StageDTO:
        """Этап, который едет на склад сотрудника. Чужой склад -> AccessDeniedError."""
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")

        if actor.employee.warehouse_id != stage.to_warehouse.id:
            # Попытка дотянуться до чужого груза — событие безопасности.
            # Пишем в техлоггер, а не в uow.history: отказ откатит транзакцию,
            # и запись в БД пропала бы вместе с ней.
            logging.warning(
                "Отказ в приёмке: сотрудник №%s (склад №%s) обратился к этапу №%s, "
                "направленному на склад №%s",
                actor.employee.id,
                actor.employee.warehouse_id,
                stage.id,
                stage.to_warehouse.id,
            )

        self._access.require_warehouse(actor, stage.to_warehouse.id)
        return stage

    def _require_shipped(self, uow: UnitOfWork, stage: StageDTO) -> None:
        if stage.status_id != self._status_id(uow, StatusName.SHIPPED):
            raise InvalidStatusError(
                f"Этап в статусе «{stage.status_name}»: "
                f"работать можно только с отправленным грузом"
            )

    @staticmethod
    def _is_discrepancy(item: StageItemDTO) -> bool:
        return item.actual_quantity is None or item.actual_quantity != item.document_quantity

    @staticmethod
    def _to_quantity(quantity: Decimal) -> Decimal:
        """Приводит количество к Decimal: из web оно приходит числом или строкой,
        а сравнивать его нужно с numeric из БД."""
        try:
            value = quantity if isinstance(quantity, Decimal) else Decimal(str(quantity))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("Количество должно быть числом") from None

        if not value.is_finite() or value < 0:
            raise ValidationError("Количество не может быть отрицательным")
        return value

    @staticmethod
    def _status_id(uow: UnitOfWork, status_name: StatusName) -> int:
        status_id = uow.statuses.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

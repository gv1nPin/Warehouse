from collections.abc import Sequence

from warehouse.api.dto import NewStageItem, StageDTO
from warehouse.bll.interfaces.shipment_service.abstract_shipment_transit_coordinator import (
    AbstractShipmentTransitCoordinator,
)
from warehouse.common import StatusName
from warehouse.common.exceptions import InvalidStatusError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork


class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    """Двигает перевозку дальше по маршруту после приёмки этапа.

    Транзакцию не открывает: uow передаёт приёмка.
    """

    def after_stage_accepted(self, uow: UnitOfWork, stage_id: int) -> None:
        stage = uow.stages.get_by_id(stage_id, with_items=True)
        if stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")

        next_stage = uow.stages.get_by_order(stage.shipment_id, stage.stage_order + 1)
        if next_stage is None:
            self._finish_shipment(uow, stage)
        else:
            self._move_to_next_stage(uow, stage, next_stage)

    def _move_to_next_stage(
        self, uow: UnitOfWork, stage: StageDTO, next_stage: StageDTO
    ) -> None:
        # Дальше едет то, что реально приняли. Факт становится документом.
        moving = [
            NewStageItem(product_id=item.product_id, quantity=item.actual_quantity)
            for item in stage.items
            if item.actual_quantity is not None and item.actual_quantity > 0
        ]

        if not moving:
            # Везти нечего: дальше по маршруту не поедет ни один этап.
            # Закрываем их все вместе с перевозкой, иначе они навсегда
            # зависнут в «В ожидании». Отдельного статуса «отменён»
            # в справочнике нет, поэтому ставим «с расхождениями».
            self._close_remaining_stages(uow, stage)
            return

        # Склад, куда пришёл этот этап, и есть транзитный: отсюда уйдёт следующий.
        transit_warehouse_id = stage.to_warehouse.id

        self._fill_next_stage(uow, next_stage.id, moving)
        self._reserve(uow, transit_warehouse_id, moving)

        uow.stages.set_status(next_stage.id, self._status_id(uow, StatusName.RESERVED))
        uow.shipments.set_status(
            stage.shipment_id, self._status_id(uow, StatusName.IN_TRANSIT_WH)
        )

    def _close_remaining_stages(self, uow: UnitOfWork, stage: StageDTO) -> None:
        """Закрывает все этапы после текущего вместе с перевозкой."""
        discrepancy_id = self._status_id(uow, StatusName.DISCREPANCY)

        for rest in uow.stages.list_by_shipment(stage.shipment_id):
            if rest.stage_order > stage.stage_order:
                uow.stages.set_status(rest.id, discrepancy_id)

        uow.shipments.set_status(stage.shipment_id, discrepancy_id)

    @staticmethod
    def _fill_next_stage(
        uow: UnitOfWork, stage_id: int, moving: Sequence[NewStageItem]
    ) -> None:
        """Переносит принятые количества в следующий этап.

        Позиции там могли быть заведены заранее (при создании черновика) —
        тогда обновляем их, а не добавляем: в БД на (stage_id, product_id)
        стоит UNIQUE. Товар, который дальше не едет, из этапа убираем.
        """
        existing = {item.product_id: item.id for item in uow.stage_items.list_by_stage(stage_id)}

        for item in moving:
            item_id = existing.get(item.product_id)
            if item_id is None:
                uow.stage_items.add(stage_id, item.product_id, item.quantity)
            else:
                uow.stage_items.set_document_quantity(item_id, item.quantity)

        moving_ids = {item.product_id for item in moving}
        for product_id, item_id in existing.items():
            if product_id not in moving_ids:
                uow.stage_items.delete(item_id)

    @staticmethod
    def _reserve(
        uow: UnitOfWork, warehouse_id: int, moving: Sequence[NewStageItem]
    ) -> None:
        """Резервирует груз на транзитном складе под следующий этап.

        Хватает ли товара, проверяем здесь: в БД стоит CHECK
        reserved_quantity <= quantity, и без проверки транзакция упала бы
        на коммите непонятной ошибкой вместо внятного отказа.
        """
        # for_update блокирует строки до конца транзакции, чтобы двое
        # не зарезервировали один и тот же товар одновременно.
        stock = uow.stock.get_many(
            warehouse_id, (item.product_id for item in moving), for_update=True
        )

        for item in moving:
            available = stock[item.product_id].available if item.product_id in stock else None
            if available is None:
                raise NotFoundError(
                    f"Товара №{item.product_id} нет на складе №{warehouse_id}"
                )
            if available < item.quantity:
                raise InvalidStatusError(
                    f"На складе №{warehouse_id} свободно {available} товара "
                    f"№{item.product_id}, а нужно {item.quantity}"
                )
            uow.stock.change(
                warehouse_id=warehouse_id,
                product_id=item.product_id,
                reserved_delta=item.quantity,
            )

    def _finish_shipment(self, uow: UnitOfWork, stage: StageDTO) -> None:
        """Последний этап принят — закрываем перевозку.

        Расхождение хотя бы на одном этапе делает такой всю перевозку.
        """
        discrepancy_id = self._status_id(uow, StatusName.DISCREPANCY)
        has_discrepancies = uow.stages.any_with_status(stage.shipment_id, [discrepancy_id])

        final_status_id = (
            discrepancy_id if has_discrepancies else self._status_id(uow, StatusName.RECEIVED)
        )
        uow.shipments.set_status(stage.shipment_id, final_status_id)

    @staticmethod
    def _status_id(uow: UnitOfWork, status_name: StatusName) -> int:
        status_id = uow.statuses.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

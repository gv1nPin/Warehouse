# shipment_transit_coordinator.py

from collections.abc import Callable

from warehouse.api.dto import NewStageItem, ShipmentDTO, StageDTO
from warehouse.bll.interfaces.shipment_service.abstract_shipment_transit_coordinator import (
    AbstractShipmentTransitCoordinator,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import AccessDeniedError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork


class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    """
    Настоящий координатор транзита отгрузок.

    Названия статусов берём из warehouse.common.StatusName,
    чтобы не искать «магические строки» по всему коду.
    """

    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
        """
        uow_factory — это функция, которая умеет создавать UoW.
        Она нужна, потому что get_shipment_progress сам открывает транзакцию.
        """
        self._uow_factory = uow_factory

    # ------------------------------------------------------------------ #
    #  ГЛАВНЫЙ МЕТОД: что делать после приёмки этапа                     #
    # ------------------------------------------------------------------ #
    def after_stage_accepted(self, uow: UnitOfWork, stage_id: int) -> None:
        """
        Вызывается внутри уже открытой транзакции (uow).
        Свою транзакцию НЕ открывает!
        """

        # Шаг 1. Достаём текущий (только что принятый) этап вместе с товарами.
        current_stage = uow.stages.get_by_id(stage_id, with_items=True)
        if current_stage is None:
            raise NotFoundError(f"Этап №{stage_id} не найден")

        # Шаг 2. Пытаемся найти СЛЕДУЮЩИЙ этап в той же отгрузке:
        # у него stage_order на 1 больше.
        next_stage = uow.stages.get_by_order(
            current_stage.shipment_id,
            current_stage.stage_order + 1,
        )

        # Шаг 3. Развилка:
        if next_stage is not None:
            # Есть следующий этап → уходим «на транзитный склад».
            self._move_to_next_stage(uow, current_stage, next_stage)
        else:
            # Следующего этапа нет → это последний этап, закрываем перевозку.
            self._finish_shipment(uow, current_stage)

    # ------------------------------------------------------------------ #
    #  ВСПОМОГАТЕЛЬНЫЙ МЕТОД: есть следующий этап                        #
    # ------------------------------------------------------------------ #
    def _move_to_next_stage(
        self, uow: UnitOfWork, current_stage: StageDTO, next_stage: StageDTO
    ) -> None:
        """Логика перехода на следующий этап (в транзит)."""

        # 1. Собираем строки, у которых факт > 0.
        #    Именно они «едут дальше». Факт становится количеством по документу.
        new_items: list[NewStageItem] = []
        for item in current_stage.items:
            if item.actual_quantity is None:
                continue
            if item.actual_quantity <= 0:
                continue
            new_items.append(
                NewStageItem(
                    product_id=item.product_id,
                    quantity=item.actual_quantity,   # факт → документ
                )
            )

        # Везти дальше нечего (всё приняли по нулям) → следующий этап остаётся
        # «В ожидании», а перевозка закрывается с расхождениями.
        if not new_items:
            uow.shipments.set_status(
                current_stage.shipment_id,
                self._status_id(uow, StatusName.DISCREPANCY),
            )
            return

        # 2. Перевозку переводим в статус «На транзитном складе».
        uow.shipments.set_status(
            current_stage.shipment_id,
            self._status_id(uow, StatusName.IN_TRANSIT_WH),
        )

        # 3. Копируем эти строки в следующий этап одной пачкой.
        uow.stage_items.add_many(next_stage.id, new_items)

        # 4. Резервируем это количество на транзитном складе —
        #    это склад, куда пришёл текущий этап (и откуда уйдёт следующий).
        transit_warehouse_id = current_stage.to_warehouse.id
        for new_item in new_items:
            changed = uow.stock.change(
                warehouse_id=transit_warehouse_id,
                product_id=new_item.product_id,
                reserved_delta=new_item.quantity,   # резерв увеличивается на +
            )
            if not changed:
                raise NotFoundError(
                    f"Нет остатка товара №{new_item.product_id} "
                    f"на складе №{transit_warehouse_id}"
                )

        # 5. Сам следующий этап переводим в статус «Зарезервировано».
        uow.stages.set_status(next_stage.id, self._status_id(uow, StatusName.RESERVED))

    # ------------------------------------------------------------------ #
    #  ВСПОМОГАТЕЛЬНЫЙ МЕТОД: следующего этапа нет                       #
    # ------------------------------------------------------------------ #
    def _finish_shipment(self, uow: UnitOfWork, current_stage: StageDTO) -> None:
        """Логика завершения перевозки."""

        # Проверяем: есть ли хотя бы один этап с расхождениями?
        discrepancy_id = self._status_id(uow, StatusName.DISCREPANCY)
        has_discrepancies = uow.stages.any_with_status(
            current_stage.shipment_id,
            [discrepancy_id],
        )

        # Выбираем финальный статус перевозки.
        if has_discrepancies:
            final_status_id = discrepancy_id
        else:
            final_status_id = self._status_id(uow, StatusName.RECEIVED)

        uow.shipments.set_status(current_stage.shipment_id, final_status_id)

    # ------------------------------------------------------------------ #
    #  ПОКАЗ ПРОГРЕССА ОТГРУЗКИ                                          #
    # ------------------------------------------------------------------ #
    def get_shipment_progress(self, employee_id: int, shipment_id: int) -> ShipmentDTO:
        """
        Вернуть отгрузку со всеми этапами, если у сотрудника есть право смотреть.
        Метод сам открывает свою транзакцию через uow_factory.
        """
        with self._uow_factory() as uow:
            # 1. Находим сотрудника.
            employee = uow.employees.get_by_id(employee_id)
            if employee is None:
                raise NotFoundError(f"Сотрудник №{employee_id} не найден или заблокирован")

            # 2. Находим отгрузку (репозиторий сразу отдаёт DTO).
            shipment = uow.shipments.get_by_id(shipment_id)
            if shipment is None:
                raise NotFoundError(f"Перевозка №{shipment_id} не найдена")

            # 3. Проверяем право на просмотр.
            is_admin = uow.employees.has_permission(employee_id, PermissionName.EMPLOYEE_MANAGE)
            in_route = self._is_employee_in_route(employee.id, employee.warehouse_id, shipment)

            if not (is_admin or in_route):
                raise AccessDeniedError("Нет прав на просмотр этой перевозки")

            return shipment

    # ------------------------------------------------------------------ #
    #  МАЛЕНЬКИЕ ХЕЛПЕРЫ                                                 #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_employee_in_route(employee_id: int, warehouse_id: int, shipment: ShipmentDTO) -> bool:
        """True, если сотрудник — водитель или приёмщик любого этапа,
        или его склад есть в маршруте."""
        for stage in shipment.stages:
            if employee_id in (stage.driver_id, stage.acceptor_id):
                return True
            if warehouse_id in (stage.from_warehouse.id, stage.to_warehouse.id):
                return True
        return False

    @staticmethod
    def _status_id(uow: UnitOfWork, status_name: StatusName) -> int:
        """id статуса по имени. Нет такого статуса в БД → понятная ошибка."""
        status_id = uow.statuses.get_id(status_name)
        if status_id is None:
            raise NotFoundError(f"В справочнике нет статуса «{status_name}»")
        return status_id

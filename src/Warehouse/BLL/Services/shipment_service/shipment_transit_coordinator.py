# ShipmentTransitCoordinator.py

from warehouse.api.dto import NewStageItem, ShipmentDTO
from warehouse.api.converters.shipment import to_shipment

from .AbstractShipmentTransitCoordinator import AbstractShipmentTransitCoordinator


class ShipmentTransitCoordinator(AbstractShipmentTransitCoordinator):
    """
    Настоящий координатор транзита отгрузок.

    Все названия статусов и роли держим в константах,
    чтобы не искать «магические строки» по всему коду.
    """

    # Названия статусов перевозки (Shipment)
    STATUS_IN_TRANSIT = "На транзитном складе"
    STATUS_ACCEPTED_WITH_DIFFS = "Принято с расхождениями"
    STATUS_ACCEPTED = "Принято"

    # Названия статусов этапа (ShipmentStage)
    STATUS_RESERVED = "Зарезервировано"
    STATUS_DISCREPANCY = "Расхождения"

    # Название роли администратора
    ROLE_ADMIN = "Администратор"

    def __init__(self, uow_factory):
        """
        uow_factory — это функция, которая умеет создавать UoW.
        Она нужна, потому что get_shipment_progress сам открывает транзакцию.
        """
        self._uow_factory = uow_factory

    # ------------------------------------------------------------------ #
    #  ГЛАВНЫЙ МЕТОД: что делать после приёмки этапа                     #
    # ------------------------------------------------------------------ #
    def after_stage_accepted(self, uow, stage_id: int) -> None:
        """
        Вызывается внутри уже открытой транзакции (uow).
        Свою транзакцию НЕ открывает!
        """

        # Шаг 1. Достаём текущий (только что принятый) этап.
        current_stage = uow.stages.get_by_id(stage_id)
        if current_stage is None:
            raise ValueError(f"Этап с id={stage_id} не найден")

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
    def _move_to_next_stage(self, uow, current_stage, next_stage) -> None:
        """Логика перехода на следующий этап (в транзит)."""

        # 1. Перевозку переводим в статус «На транзитном складе».
        transit_status = uow.statuses.get_by_name(self.STATUS_IN_TRANSIT)
        uow.shipments.update_status(
            current_stage.shipment_id,
            transit_status.id,
        )

        # 2. Собираем строки, у которых факт > 0.
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

        # 3. Копируем эти строки в следующий этап одной пачкой.
        if new_items:
            uow.stage_items.add_many(next_stage.id, new_items)

        # 4. На транзитном складе (склад-получатель следующего этапа)
        #    резервируем это количество.
        for new_item in new_items:
            uow.stock.change(
                warehouse_id=next_stage.to_warehouse_id,
                product_id=new_item.product_id,
                reserved_delta=new_item.quantity,   # резерв увеличивается на +
            )

        # 5. Сам следующий этап переводим в статус «Зарезервировано».
        reserved_status = uow.statuses.get_by_name(self.STATUS_RESERVED)
        uow.stages.update_status(next_stage.id, reserved_status.id)

    # ------------------------------------------------------------------ #
    #  ВСПОМОГАТЕЛЬНЫЙ МЕТОД: следующего этапа нет                       #
    # ------------------------------------------------------------------ #
    def _finish_shipment(self, uow, current_stage) -> None:
        """Логика завершения перевозки."""

        # Проверяем: есть ли хотя бы один этап с расхождениями?
        discrepancy_status = uow.statuses.get_by_name(self.STATUS_DISCREPANCY)
        has_discrepancies = uow.stages.any_with_status(
            current_stage.shipment_id,
            discrepancy_status.id,
        )

        # Выбираем финальный статус перевозки.
        if has_discrepancies:
            final_status = uow.statuses.get_by_name(self.STATUS_ACCEPTED_WITH_DIFFS)
        else:
            final_status = uow.statuses.get_by_name(self.STATUS_ACCEPTED)

        uow.shipments.update_status(current_stage.shipment_id, final_status.id)

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
                raise ValueError(f"Сотрудник с id={employee_id} не найден")

            # 2. Находим отгрузку.
            shipment = uow.shipments.get_by_id(shipment_id)
            if shipment is None:
                raise ValueError(f"Отгрузка с id={shipment_id} не найдена")

            # 3. Проверяем право на просмотр.
            is_admin = employee.role_name == self.ROLE_ADMIN
            in_route = self._is_employee_in_route(employee, shipment)

            if not (is_admin or in_route):
                raise PermissionError("Нет прав на просмотр этой отгрузки")

            # 4. Преобразуем ORM-сущность в DTO и отдаём наружу.
            return to_shipment(shipment)

    # ------------------------------------------------------------------ #
    #  МАЛЕНЬКИЙ ХЕЛПЕР: участвует ли сотрудник в маршруте               #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _is_employee_in_route(employee, shipment) -> bool:
        """True, если сотрудник — водитель или приёмщик любого этапа."""
        for stage in shipment.stages:
            if stage.driver_id == employee.id:
                return True
            if stage.acceptor_id == employee.id:
                return True
        return False
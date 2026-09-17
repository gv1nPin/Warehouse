# RouteQueryService.py

from warehouse.api.dto import StageDTO
from warehouse.api.converters.shipment import to_stage

from .AbstractRouteQueryService import AbstractRouteQueryService, AccessDeniedError


class RouteQueryService(AbstractRouteQueryService):
    """
    Настоящий сервис просмотра маршрутов.

    Главная идея: у сотрудника может быть несколько «ролей» (прав).
    Проверяем их по очереди — от самых «широких» к самым «узким».
    """

    # Названия прав (permissions). Держим их константами,
    # чтобы не писать строки «руками» по всему коду.
    PERM_MANAGE = "employee:manage"      # полный доступ ко всему
    PERM_CREATE = "shipment:create"      # создаёт отгрузки
    PERM_ACCEPT = "shipment:accept"      # принимает отгрузки

    def __init__(self, uow_factory):
        """
        uow_factory — функция, которая создаёт Unit of Work (транзакцию).
        Мы её вызываем, когда нужно самим открыть транзакцию.
        """
        self._uow_factory = uow_factory

    # ------------------------------------------------------------------ #
    #  ПУБЛИЧНЫЙ МЕТОД 1: список маршрутов                                #
    # ------------------------------------------------------------------ #
    def list_routes(self, employee_id: int, only_active: bool = False) -> list[StageDTO]:
        """Список маршрутов, доступных сотруднику."""

        # Открываем свою транзакцию (метод её не принимает аргументом).
        with self._uow_factory() as uow:

            # 1. Находим сотрудника.
            employee = uow.employees.get_by_id(employee_id)
            if employee is None:
                raise AccessDeniedError(f"Сотрудник id={employee_id} не найден")

            # 2. Узнаём список прав сотрудника (например: ["shipment:create"]).
            permissions = uow.permissions.list_for_employee(employee_id)

            # 3. Выбираем, как именно искать маршруты.
            stages = self._pick_stages_for_listing(
                uow, employee, permissions, only_active
            )

            # 4. ORM-объекты превращаем в DTO и отдаём наружу.
            #    with_items=False — в списке товары не нужны, только шапки.
            return [to_stage(st, with_items=False) for st in stages]

    # ------------------------------------------------------------------ #
    #  ПУБЛИЧНЫЙ МЕТОД 2: один маршрут                                    #
    # ------------------------------------------------------------------ #
    def get_route(self, employee_id: int, stage_id: int) -> StageDTO:
        """Один маршрут вместе с товарами. Доступ — по тем же правилам."""

        with self._uow_factory() as uow:

            # 1. Сотрудник.
            employee = uow.employees.get_by_id(employee_id)
            if employee is None:
                raise AccessDeniedError(f"Сотрудник id={employee_id} не найден")

            # 2. Права.
            permissions = uow.permissions.list_for_employee(employee_id)

            # 3. Находим сам этап.
            stage = uow.stages.get_by_id(stage_id)
            if stage is None:
                raise AccessDeniedError(f"Маршрут id={stage_id} не найден")

            # 4. Проверяем, имеет ли сотрудник право смотреть ИМЕННО этот этап.
            if not self._can_view_stage(uow, employee, permissions, stage):
                raise AccessDeniedError("Нет прав на просмотр этого маршрута")

            # 5. Отдаём DTO вместе с товарами (with_items=True).
            return to_stage(stage, with_items=True)

    # ================================================================== #
    #  ВНУТРЕННИЕ ХЕЛПЕРЫ                                                 #
    # ================================================================== #

    def _pick_stages_for_listing(self, uow, employee, permissions, only_active):
        """
        Решает, какой запрос к репозиторию сделать,
        в зависимости от прав сотрудника.
        """
        # --- Случай 1: полный доступ. Все маршруты. ---
        if self.PERM_MANAGE in permissions:
            return uow.stages.list_all(only_active=only_active)

        # --- Случай 2: может создавать или принимать отгрузки.
        #     Значит, видит маршруты СВОЕГО склада. ---
        if self.PERM_CREATE in permissions or self.PERM_ACCEPT in permissions:
            return uow.stages.list_for_warehouse(
                warehouse_id=employee.warehouse_id,
                only_active=only_active,
            )

        # --- Случай 3: сотрудник назначен водителем хоть где-то.
        #     Показываем ТОЛЬКО его активные маршруты. ---
        driver_stages = uow.stages.list_for_driver(
            driver_id=employee.id,
            only_active=True,           # водителю — только активные
        )
        if driver_stages:
            return driver_stages

        # --- Случай 4: ничего из перечисленного — отказать. ---
        raise AccessDeniedError("Нет прав на просмотр маршрутов")

    def _can_view_stage(self, uow, employee, permissions, stage) -> bool:
        """
        True, если сотруднику разрешено видеть этот конкретный этап.
        Логика ровно такая же, как в _pick_stages_for_listing,
        только проверяем ОДИН этап, а не список.
        """
        # 1. Полный доступ.
        if self.PERM_MANAGE in permissions:
            return True

        # 2. Свой склад.
        if self.PERM_CREATE in permissions or self.PERM_ACCEPT in permissions:
            # Этап касается склада сотрудника?
            # (склад может быть либо "откуда", либо "куда").
            if stage.from_warehouse_id == employee.warehouse_id:
                return True
            if stage.to_warehouse_id == employee.warehouse_id:
                return True

        # 3. Он — водитель этого этапа.
        if stage.driver_id == employee.id:
            return True

        # 4. Ничего не подошло.
        return False
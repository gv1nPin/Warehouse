# route_query_service.py

from collections.abc import Callable

from warehouse.api.dto import EmployeeDTO, StageDTO
from warehouse.bll.interfaces.shipment_service.abstract_route_query_service import (
    AbstractRouteQueryService,
)
from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import AccessDeniedError, NotFoundError
from warehouse.dal.unit_of_work import UnitOfWork

# Активные маршруты — те, что ещё не приняты.
ACTIVE_STATUSES = (
    StatusName.DRAFT,
    StatusName.WAITING,
    StatusName.RESERVED,
    StatusName.SHIPPED,
)


class RouteQueryService(AbstractRouteQueryService):
    """
    Настоящий сервис просмотра маршрутов.

    Главная идея: у сотрудника может быть несколько «ролей» (прав).
    Проверяем их по очереди — от самых «широких» к самым «узким».
    """

    # Названия прав (permissions) берём из warehouse.common.PermissionName,
    # чтобы не писать строки «руками» по всему коду.
    PERM_MANAGE = PermissionName.EMPLOYEE_MANAGE   # полный доступ ко всему
    PERM_CREATE = PermissionName.SHIPMENT_CREATE   # создаёт отгрузки
    PERM_ACCEPT = PermissionName.SHIPMENT_ACCEPT   # принимает отгрузки

    def __init__(self, uow_factory: Callable[[], UnitOfWork]):
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
            employee = self._get_employee(uow, employee_id)

            # 2. Узнаём список прав сотрудника (например: {"shipment:create"}).
            permissions = set(uow.employees.get_permissions(employee_id))

            # 3. Выбираем, как именно искать маршруты.
            #    Репозиторий сразу отдаёт DTO, товары в списке не нужны — только шапки.
            return self._pick_stages_for_listing(uow, employee, permissions, only_active)

    # ------------------------------------------------------------------ #
    #  ПУБЛИЧНЫЙ МЕТОД 2: один маршрут                                    #
    # ------------------------------------------------------------------ #
    def get_route(self, employee_id: int, stage_id: int) -> StageDTO:
        """Один маршрут вместе с товарами. Доступ — по тем же правилам."""

        with self._uow_factory() as uow:

            # 1. Сотрудник.
            employee = self._get_employee(uow, employee_id)

            # 2. Права.
            permissions = set(uow.employees.get_permissions(employee_id))

            # 3. Находим сам этап (сразу с товарами).
            stage = uow.stages.get_by_id(stage_id, with_items=True)
            if stage is None:
                raise NotFoundError(f"Маршрут №{stage_id} не найден")

            # 4. Проверяем, имеет ли сотрудник право смотреть ИМЕННО этот этап.
            if not self._can_view_stage(employee, permissions, stage):
                raise AccessDeniedError("Нет прав на просмотр этого маршрута")

            return stage

    # ================================================================== #
    #  ВНУТРЕННИЕ ХЕЛПЕРЫ                                                 #
    # ================================================================== #

    @staticmethod
    def _get_employee(uow: UnitOfWork, employee_id: int) -> EmployeeDTO:
        employee = uow.employees.get_by_id(employee_id)
        if employee is None:
            raise NotFoundError(f"Сотрудник №{employee_id} не найден или заблокирован")
        return employee

    @staticmethod
    def _active_status_ids(uow: UnitOfWork) -> list[int]:
        """id активных статусов (статусы ищем по имени, а не по числу)."""
        ids = [uow.statuses.get_id(name) for name in ACTIVE_STATUSES]
        return [status_id for status_id in ids if status_id is not None]

    def _pick_stages_for_listing(
        self, uow: UnitOfWork, employee: EmployeeDTO, permissions: set[str], only_active: bool
    ) -> list[StageDTO]:
        """
        Решает, какой запрос к репозиторию сделать,
        в зависимости от прав сотрудника.
        """
        # None — без фильтра по статусам.
        status_ids = self._active_status_ids(uow) if only_active else None

        # --- Случай 1: полный доступ. Все маршруты. ---
        if self.PERM_MANAGE in permissions:
            return uow.stages.list_all(status_ids=status_ids)

        # --- Случай 2: может создавать или принимать отгрузки.
        #     Значит, видит маршруты СВОЕГО склада. ---
        if self.PERM_CREATE in permissions or self.PERM_ACCEPT in permissions:
            return uow.stages.list_for_warehouse(
                warehouse_id=employee.warehouse_id,
                status_ids=status_ids,
            )

        # --- Случай 3: сотрудник назначен водителем хоть где-то.
        #     Показываем ТОЛЬКО его активные маршруты. ---
        driver_stages = uow.stages.list_for_driver(
            driver_id=employee.id,
            status_ids=self._active_status_ids(uow),   # водителю — только активные
        )
        if driver_stages:
            return driver_stages

        # --- Случай 4: ничего из перечисленного — отказать. ---
        raise AccessDeniedError("Нет прав на просмотр маршрутов")

    def _can_view_stage(
        self, employee: EmployeeDTO, permissions: set[str], stage: StageDTO
    ) -> bool:
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
            if employee.warehouse_id in (stage.from_warehouse.id, stage.to_warehouse.id):
                return True

        # 3. Он — водитель этого этапа.
        if stage.driver_id == employee.id:
            return True

        # 4. Ничего не подошло.
        return False

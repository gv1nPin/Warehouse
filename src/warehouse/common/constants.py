"""Имена из справочников БД. В коде id не хардкодим, ищем по имени:

    uow.statuses.get_id(StatusName.DRAFT)
    uow.roles.get_id(RoleName.ADMIN)

Строки должны совпадать с БД символ в символ, включая часть в скобках.
"""

from enum import StrEnum


class RoleName(StrEnum):
    """Roles.role_name"""

    SENIOR_STOREKEEPER = "Старший кладовщик"   # черновики, резерв и отправка, приёмка
    STOREKEEPER = "Кладовщик"                  # резерв и отправка, приёмка
    MANAGER = "Менеджер"                       # смотрит все перевозки, отменяет
    DRIVER = "Водитель"                        # везёт этап, видит только свои рейсы
    ADMIN = "Администратор системы"            # суперпользователь: все права, все склады


class PermissionName(StrEnum):
    """Permissions.permission_name"""

    SHIPMENT_CREATE = "shipment:create"       # маршрут, черновик, товары, водитель, документы
    SHIPMENT_ACCEPT = "shipment:accept"       # ввод факта и приёмка
    EMPLOYEE_MANAGE = "employee:manage"       # регистрация и блокировка сотрудников
    SHIPMENT_DISPATCH = "shipment:dispatch"   # резерв и отправка
    SHIPMENT_CANCEL = "shipment:cancel"       # отмена перевозки
    SHIPMENT_VIEW_ALL = "shipment:view_all"   # перевозки всех складов


class StatusName(StrEnum):
    """Statuses.status_name. Одни и те же статусы у перевозки (Shipments) и у этапа (ShipmentStages)."""

    DRAFT = "Черновик (Draft)"
    SHIPPED = "Отправлено (Shipped)"
    RECEIVED = "Принято (Received)"
    RESERVED = "Зарезервировано (Reserved)"
    WAITING = "В ожидании (In Waiting)"
    DISCREPANCY = "Принято с расхождениями (Discrepancy)"
    IN_TRANSIT_WH = "На транзитном складе (In Transit WH)"
    CANCELLED = "Отменено (Cancelled)"


class OperationType(StrEnum):
    """operation_history.operation_type: что сделал сотрудник."""

    LOGIN = "auth.login"
    EMPLOYEE_REGISTER = "employee.register"
    SHIPMENT_CREATE = "shipment.create"
    SHIPMENT_DELETE = "shipment.delete"
    SHIPMENT_CANCEL = "shipment.cancel"
    ITEM_ADD = "stage.item_add"
    ITEM_REMOVE = "stage.item_remove"
    DRIVER_ASSIGN = "stage.driver"
    DOCUMENT_ATTACH = "stage.document_attach"
    DOCUMENT_REMOVE = "stage.document_remove"
    STAGE_RESERVE = "stage.reserve"
    STAGE_SHIP = "stage.ship"
    FACT_ENTER = "stage.fact"
    STAGE_ACCEPT = "stage.accept"


class EntityName(StrEnum):
    """operation_history.entity_name: над чем выполнена операция."""

    EMPLOYEE = "Employee"
    SHIPMENT = "Shipment"
    STAGE = "ShipmentStage"
    ITEM = "StageItem"

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

"""Имена из справочников БД. В коде id не хардкодим, ищем по имени:

    uow.statuses.get_id(StatusName.DRAFT)
    uow.roles.get_id(RoleName.ADMIN)

Строки должны совпадать с БД символ в символ, включая часть в скобках.
"""

from enum import StrEnum


class RoleName(StrEnum):
    """Roles.role_name"""

    SENIOR_STOREKEEPER = "Старший кладовщик"   # создаёт отправки и принимает
    ADMIN = "Администратор системы"            # управляет сотрудниками


class PermissionName(StrEnum):
    """Permissions.permission_name"""

    SHIPMENT_CREATE = "shipment:create"   # маршрут, черновик, товары, отправка
    SHIPMENT_ACCEPT = "shipment:accept"   # ввод факта и приёмка
    EMPLOYEE_MANAGE = "employee:manage"   # регистрация и блокировка сотрудников


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

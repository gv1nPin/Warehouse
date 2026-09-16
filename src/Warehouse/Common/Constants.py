from enum import StrEnum


class RoleName(StrEnum):
    """Значения Roles.role_name."""

    ADMIN = "Администратор"
    STOREKEEPER = "Кладовщик"
    DRIVER = "Водитель"


class StatusName(StrEnum):
    """Значения Statuses.status_name."""

    CREATED = "Создана"
    IN_TRANSIT = "В пути"
    RECEIVED = "Получена"
    CANCELLED = "Отменена"


ACTIVE_STATUSES = (StatusName.CREATED, StatusName.IN_TRANSIT)

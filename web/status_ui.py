"""UI-хелперы для статусов StageDTO / ShipmentDTO.

В DTO поле status_name — полное имя из БД (StatusName.*), например
«Черновик (Draft)». Для CSS и коротких подписей маппим отдельно.
"""
from __future__ import annotations

from warehouse.common import StatusName

# StatusName.value → класс плашки в cabinet.css / app.css
STATUS_CSS: dict[str, str] = {
    StatusName.DRAFT: "draft",
    StatusName.WAITING: "waiting",
    StatusName.RESERVED: "reserved",
    StatusName.SHIPPED: "shipped",
    StatusName.RECEIVED: "received",
    StatusName.DISCREPANCY: "discrepancy",
    StatusName.CANCELLED: "cancelled",
    StatusName.IN_TRANSIT_WH: "waiting",
}

STATUS_FILTERS: list[tuple[str, str]] = [
    ("all", "Все"),
    (StatusName.DRAFT, "Черновик"),
    (StatusName.RESERVED, "Зарезервировано"),
    (StatusName.SHIPPED, "Отправлено"),
    (StatusName.DISCREPANCY, "С расхождениями"),
    (StatusName.RECEIVED, "Принято"),
    (StatusName.CANCELLED, "Отменено"),
]


def status_label(status_name: str | None) -> str:
    """«Черновик (Draft)» → «Черновик»."""
    if not status_name:
        return ""
    if " (" in status_name:
        return status_name.split(" (", 1)[0]
    return status_name


def status_css(status_name: str | None) -> str:
    """Класс для .pill.st-*: draft / reserved / …"""
    if not status_name:
        return "draft"
    return STATUS_CSS.get(status_name, "draft")


def normalize_status_query(value: str | None) -> str:
    """GET ?status= может быть коротким ключом или полным StatusName."""
    if not value or value == "all":
        return "all"
    short_to_full = {css: name for name, css in STATUS_CSS.items()}
    if value in short_to_full:
        return short_to_full[value]
    return value

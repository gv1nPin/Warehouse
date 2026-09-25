from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format
from django.utils.html import format_html

from warehouse.common import StatusName

register = template.Library()

STATUS_CLASSES = {
    StatusName.DRAFT: 'st-draft',
    StatusName.WAITING: 'st-waiting',
    StatusName.RESERVED: 'st-reserved',
    StatusName.SHIPPED: 'st-shipped',
    StatusName.IN_TRANSIT_WH: 'st-shipped',
    StatusName.RECEIVED: 'st-received',
    StatusName.DISCREPANCY: 'st-discrepancy',
    StatusName.CANCELLED: 'st-cancelled',
}

FRACTIONAL_UNITS = {'т', 'кг'}


@register.filter
def status_class(status_name: str) -> str:
    """Имя статуса из БД -> CSS-класс плашки."""
    return STATUS_CLASSES.get(status_name, 'st-waiting')


@register.filter
def status_label(status_name: str) -> str:
    """Имя статуса без английской части в скобках."""
    return (status_name or '').split(' (')[0]


@register.filter
def qty(value, unit: str = '') -> str:
    """Количество с единицей: для т и кг три знака после запятой, остальное целым."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    digits = 3 if unit in FRACTIONAL_UNITS else 0
    text = number_format(number, decimal_pos=digits, use_l10n=True, force_grouping=True)
    return f'{text} {unit}'.strip()


@register.simple_tag
def status_pill(status_name: str) -> str:
    """Готовая плашка статуса."""
    return format_html(
        '<span class="pill {}">{}</span>', status_class(status_name), status_label(status_name)
    )

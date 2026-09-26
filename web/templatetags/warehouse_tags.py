import json
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format
from django.utils.html import format_html

from warehouse.common import OperationType, StatusName

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

FRACTIONAL_UNITS = {'т', 'кг', 'л'}

OPERATION_LABELS = {
    OperationType.LOGIN: 'Вход в систему',
    OperationType.EMPLOYEE_REGISTER: 'Регистрация сотрудника',
    OperationType.SHIPMENT_CREATE: 'Создание черновика',
    OperationType.SHIPMENT_DELETE: 'Удаление черновика',
    OperationType.SHIPMENT_CANCEL: 'Отмена перевозки',
    OperationType.ITEM_ADD: 'Товар добавлен',
    OperationType.ITEM_REMOVE: 'Товар убран',
    OperationType.DRIVER_ASSIGN: 'Водитель',
    OperationType.DOCUMENT_ATTACH: 'Документ прикреплён',
    OperationType.DOCUMENT_REMOVE: 'Документ откреплён',
    OperationType.STAGE_RESERVE: 'Резерв',
    OperationType.STAGE_SHIP: 'Отправка',
    OperationType.FACT_ENTER: 'Ввод факта',
    OperationType.STAGE_ACCEPT: 'Приёмка',
}


@register.filter
def status_class(status_name: str) -> str:
    """Имя статуса из БД -> CSS-класс плашки."""
    return STATUS_CLASSES.get(status_name, 'st-waiting')


@register.filter
def status_label(status_name: str) -> str:
    """Имя статуса без английской части в скобках."""
    return (status_name or '').split(' (')[0]


@register.filter
def amount(value, unit: str = '') -> str:
    """Число без единицы: для т, кг и л три знака после запятой, остальное целым."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value
    digits = 3 if unit in FRACTIONAL_UNITS else 0
    return number_format(number, decimal_pos=digits, use_l10n=True, force_grouping=True)


@register.filter
def qty(value, unit: str = '') -> str:
    """Количество с единицей: для т, кг и л три знака после запятой, остальное целым."""
    return f'{amount(value, unit)} {unit}'.strip()


@register.filter
def short_name(full_name: str | None) -> str:
    """«Петров Сергей» -> «Петров С.»."""
    last, _, first = (full_name or '').partition(' ')
    return f'{last} {first[0]}.' if first else last


@register.filter
def file_ext(file_name: str) -> str:
    """Расширение файла для значка: «ТОРГ-12.pdf» -> «PDF»."""
    _, dot, ext = (file_name or '').rpartition('.')
    return ext.upper()[:4] if dot else ''


@register.filter
def unfilled_count(items) -> int:
    """Сколько позиций этапа ещё без факта."""
    return sum(1 for item in items if item.actual_quantity is None)


@register.filter
def operation_label(operation_type: str) -> str:
    """Код операции из журнала -> подпись для человека."""
    return OPERATION_LABELS.get(operation_type, operation_type)


@register.filter
def as_json(details: dict | None) -> str:
    """Детали записи журнала одной строкой JSON."""
    return json.dumps(details, ensure_ascii=False) if details else ''


@register.simple_tag
def status_pill(status_name: str) -> str:
    """Готовая плашка статуса."""
    return format_html(
        '<span class="pill {}">{}</span>', status_class(status_name), status_label(status_name)
    )

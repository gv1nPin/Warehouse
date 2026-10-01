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


@register.filter
def format_details(details: dict | None, operation_type: str) -> str:
    """Превращает структурированный JSON деталей операции в красивую строку для человека."""
    if not details:
        return ""

    try:
        # Водитель
        if operation_type == OperationType.DRIVER_ASSIGN:
            action = "Переназначен" if details.get("action_type") == "reassigned" else "Назначен"
            driver = f"водитель №{details['driver_id']}" if details.get("driver_id") else "водитель снят"
            return f"{action}: {driver}"

        # Регистрация сотрудника
        if operation_type == OperationType.EMPLOYEE_REGISTER:
            wh_id = details.get('warehouse_id') or details.get('warehouse')
            warehouse_str = f" на склад №{wh_id}" if wh_id else ""
            return f"Зарегистрирован пользователь «{details.get('login')}» (Роль №{details.get('role_id')}){warehouse_str}"


        # Создание черновика
        if operation_type == OperationType.SHIPMENT_CREATE:
            route_str = " → ".join(str(w_id) for w_id in details.get("route", []))
            return (
                f"Маршрут: {route_str} | Дата: {details.get('planned_date')} | "
                f"Позиций: {details.get('total_items', 0)} | Документов: {details.get('documents_count', 0)}"
            )

        # Товар добавлен
        if operation_type == OperationType.ITEM_ADD:
            mode = "с заменой количества" if details.get("is_replaced") else "новая позиция"
            return f"Товар №{details.get('product_id')} | Кол-во: {details.get('quantity')} ({mode})"

        # Резерв
        if operation_type == OperationType.STAGE_RESERVE:
            # Считаем количество зарезервированных позиций в списке items
            items_count = len(details.get("items", [])) if isinstance(details.get("items"), list) else 0
            return f"Зарезервировано позиций: {items_count}"

        # Отправка
        if operation_type == OperationType.STAGE_SHIP:
            items_list = details.get("items", [])
            positions_count = len(items_list) if isinstance(items_list, list) else 0
            
            total_qty = 0
            if isinstance(items_list, list):
                for item in items_list:
                    try:
                        total_qty += float(item.get("quantity", 0))
                    except (ValueError, TypeError):
                        pass
            
            total_qty_str = f"{total_qty:g}" if total_qty % 1 != 0 else f"{int(total_qty)}"
            return (
                f"Перевозка №{details.get('shipment_id')} | "
                f"Со склада №{details.get('from_warehouse_id')} на склад №{details.get('to_warehouse_id')} | "
                f"Отправлено: {positions_count} поз. ({total_qty_str} шт.)"
            )


        # Документ прикреплён
        if operation_type == OperationType.DOCUMENT_ATTACH:
            return f"Прикреплён файл «{details.get('file_name')}» (ID документа: {details.get('document_id')})"

        # Документ откреплён
        if operation_type == OperationType.DOCUMENT_REMOVE:
            return f"Откреплён файл «{details.get('file_name')}»"

    except Exception:
        pass

    return ", ".join(f"{k}: {value}" for k, value in details.items() if not k.startswith("_"))



@register.simple_tag
def status_pill(status_name: str) -> str:
    """Готовая плашка статуса."""
    return format_html(
        '<span class="pill {}">{}</span>', status_class(status_name), status_label(status_name)
    )

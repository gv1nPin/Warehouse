import json
from datetime import datetime
from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from ..auth import employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http
from ..services import history_service
from ..templatetags.warehouse_tags import as_json, operation_label

PAGE_SIZE = 50
EXPORT_PAGE = 500
EXPORT_LIMIT = 5000
FILTER_FIELDS = ('employee_id', 'operation_type', 'entity_name', 'entity_id', 'since', 'until')
EXPORT_COLUMNS = (
    ('№', 8), ('Время', 20), ('ID сотрудника', 14), ('Сотрудник', 28), ('Операция', 24),
    ('Код операции', 22), ('Сущность', 16), ('ID сущности', 12), ('Детали', 60),
)


def _moment(raw: str) -> datetime | None:
    """Дата из поля datetime-local во времени проекта; неверная — без фильтра."""
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return timezone.make_aware(datetime.strptime(raw, fmt))
        except ValueError:
            continue
    return None


def journal_filters(request) -> tuple[dict[str, str], dict]:
    """Введённые значения фильтров и готовые аргументы для list_operations."""
    raw = {name: request.GET.get(name, '').strip() for name in FILTER_FIELDS}
    return raw, {
        'actor_employee_id': int(raw['employee_id']) if raw['employee_id'].isdigit() else None,
        'operation_type': raw['operation_type'] or None,
        'entity_name': raw['entity_name'] or None,
        'entity_id': int(raw['entity_id']) if raw['entity_id'].isdigit() else None,
        'since': _moment(raw['since']),
        'until': _moment(raw['until']),
    }


def _workbook(operations) -> bytes:
    """Excel-файл журнала: одна строка на запись."""
    book = Workbook()
    sheet = book.active
    sheet.title = 'Журнал операций'
    sheet.append([title for title, _ in EXPORT_COLUMNS])
    for column, (_, width) in enumerate(EXPORT_COLUMNS, start=1):
        sheet.cell(1, column).font = Font(bold=True)
        sheet.column_dimensions[get_column_letter(column)].width = width
    for op in operations:
        sheet.append([
            op.id,
            timezone.localtime(op.created_at).strftime('%d.%m.%Y %H:%M:%S'),
            op.employee_id,
            op.employee_name,
            operation_label(op.operation_type),
            op.operation_type,
            op.entity_name,
            op.entity_id,
            as_json(op.details),
        ])
    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


@require_GET
@employee_required
@business_errors_as_http
@logged
def operations_list_view(request):
    """Журнал операций для администратора с фильтрами и постраничным просмотром."""
    raw, filters = journal_filters(request)
    raw_page = request.GET.get('page', '')
    page = int(raw_page) if raw_page.isdigit() and int(raw_page) > 0 else 1
    service = history_service()
    employee_id = request.actor.employee_id
    operations = service.list_operations(
        employee_id, **filters, limit=PAGE_SIZE + 1, offset=(page - 1) * PAGE_SIZE
    )
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'web/operations/list.html', {
        'operations': operations[:PAGE_SIZE],
        'raw': raw,
        'choices': service.list_filters(employee_id),
        'page': page,
        'has_next': len(operations) > PAGE_SIZE,
        'query': params.urlencode(),
    })


@require_GET
@employee_required
@business_errors_as_http
@logged
def operation_detail_view(request, operation_id: int):
    """Одна запись журнала с деталями."""
    operation = history_service().get_operation(request.actor.employee_id, operation_id)
    details = json.dumps(operation.details, ensure_ascii=False, indent=2) if operation.details else ''
    return render(request, 'web/operations/detail.html', {'op': operation, 'details': details})


@require_GET
@employee_required
@business_errors_as_http
@logged
def operations_export_view(request):
    """Выгрузка журнала в Excel с теми же фильтрами, что у списка, до 5000 строк."""
    _, filters = journal_filters(request)
    service = history_service()
    operations = []
    while len(operations) < EXPORT_LIMIT:
        batch = service.list_operations(
            request.actor.employee_id, **filters, limit=EXPORT_PAGE, offset=len(operations)
        )
        operations.extend(batch)
        if len(batch) < EXPORT_PAGE:
            break
    stamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(
        _workbook(operations[:EXPORT_LIMIT]),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="operation_history_{stamp}.xlsx"'
    return response

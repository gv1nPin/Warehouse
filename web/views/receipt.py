from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from warehouse.common import StatusName
from warehouse.common.exceptions import BusinessError

from ..auth import employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http, business_errors_as_messages
from ..services import receipt_service

FACT_PREFIX = 'fact_'


def _number(raw: str) -> str:
    """Количество из поля ввода: запятая как точка, без пробелов; проверяет сервис."""
    return raw.replace(',', '.').replace(' ', '').replace('\xa0', '').strip()


def _positions(count: int) -> str:
    """«по 1 позиции», «по 5 позициям»."""
    return 'позиции' if count % 10 == 1 and count % 100 != 11 else 'позициям'


@require_GET
@employee_required
@business_errors_as_http
@logged
def receipt_list_view(request):
    """Этапы «Отправлено», которые едут на склад сотрудника."""
    stages = receipt_service().get_incoming(request.actor.employee_id)
    return render(request, 'web/receipt/list.html', {'stages': stages})


@require_POST
@employee_required
@business_errors_as_messages
@logged
def save_facts_view(request, stage_id: int):
    """Сохраняет факт по заполненным позициям; ошибка одной позиции не останавливает остальные."""
    service = receipt_service()
    employee_id = request.actor.employee_id
    names = {
        item.id: item.product_name
        for stage in service.get_incoming(employee_id) if stage.id == stage_id
        for item in stage.items
    }
    saved = 0
    for key, value in request.POST.items():
        raw_id = key.removeprefix(FACT_PREFIX)
        if not key.startswith(FACT_PREFIX) or not raw_id.isdigit() or not value.strip():
            continue
        item_id = int(raw_id)
        try:
            service.enter_actual_quantity(employee_id, item_id, _number(value), request.POST.get(f'comment_{item_id}'))
        except BusinessError as exc:
            messages.error(request, f'{names.get(item_id, f"Позиция №{item_id}")}: {exc.message}')
        else:
            saved += 1
    if saved:
        messages.success(request, f'Факт сохранён по {saved} {_positions(saved)}')
    return redirect('receipt')


@require_POST
@employee_required
@business_errors_as_messages
@logged
def accept_view(request, stage_id: int):
    """Закрывает приёмку этапа и приходует товар на склад."""
    stage = receipt_service().accept_stage(request.actor.employee_id, stage_id)
    discrepancy = stage.status_name == StatusName.DISCREPANCY
    messages.success(request, 'Этап принят с расхождениями' if discrepancy else 'Этап принят')
    return redirect('receipt')

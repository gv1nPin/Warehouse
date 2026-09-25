from django.views.decorators.http import require_GET, require_POST

from ..auth import employee_required
from ._stub import stub_action, stub_page


@require_GET
@employee_required
def receipt_list_view(request):
    """Входящие этапы для приёмки."""
    return stub_page(request, 'Приёмка')


@require_POST
@employee_required
def save_facts_view(request, stage_id: int):
    """Сохраняет фактические количества этапа."""
    return stub_action(request, 'Ввод факта')


@require_POST
@employee_required
def accept_view(request, stage_id: int):
    """Принимает этап на складе назначения."""
    return stub_action(request, 'Приёмка этапа')

from django.views.decorators.http import require_GET, require_POST

from ..auth import employee_required
from ._stub import stub_action, stub_page


@require_GET
@employee_required
def shipment_detail_view(request, shipment_id: int):
    """Карточка перевозки со всеми этапами."""
    return stub_page(request, f'Перевозка №{shipment_id}')


@require_POST
@employee_required
def reserve_view(request, stage_id: int):
    """Резервирует товар этапа на складе отправления."""
    return stub_action(request, 'Резерв этапа')


@require_POST
@employee_required
def ship_view(request, stage_id: int):
    """Отправляет этап со склада."""
    return stub_action(request, 'Отправка этапа')


@require_POST
@employee_required
def cancel_view(request, shipment_id: int):
    """Отменяет перевозку до отправки."""
    return stub_action(request, 'Отмена перевозки')


@require_GET
@employee_required
def document_open_view(request, stage_id: int, document_id: int):
    """Отдаёт файл документа этапа."""
    return stub_page(request, 'Документ')

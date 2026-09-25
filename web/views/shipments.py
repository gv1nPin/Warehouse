from django.views.decorators.http import require_GET

from ..auth import employee_required
from ._stub import stub_page


@require_GET
@employee_required
def shipment_list_view(request):
    """Список перевозок с фильтрами и поиском."""
    return stub_page(request, 'Перевозки')

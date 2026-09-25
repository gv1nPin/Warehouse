from django.views.decorators.http import require_GET

from ..auth import employee_required
from ._stub import stub_page


@require_GET
@employee_required
def home_view(request):
    """Главная: счётчики и плитки разделов."""
    return stub_page(request, 'Главная')


@require_GET
@employee_required
def stock_view(request):
    """Остатки склада сотрудника."""
    return stub_page(request, 'Остатки')

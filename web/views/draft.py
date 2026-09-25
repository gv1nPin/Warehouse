from django.views.decorators.http import require_http_methods, require_POST

from ..auth import employee_required
from ._stub import stub_action, stub_page


@require_http_methods(['GET', 'POST'])
@employee_required
def draft_create_view(request):
    """Форма создания черновика перевозки."""
    return stub_page(request, 'Новая перевозка')


@require_POST
@employee_required
def add_item_view(request, stage_id: int):
    """Добавляет товар в этап-черновик."""
    return stub_action(request, 'Добавление товара')


@require_POST
@employee_required
def remove_item_view(request, item_id: int):
    """Убирает товар из этапа-черновика."""
    return stub_action(request, 'Удаление товара')


@require_POST
@employee_required
def assign_driver_view(request, stage_id: int):
    """Назначает или снимает водителя этапа."""
    return stub_action(request, 'Назначение водителя')


@require_POST
@employee_required
def attach_document_view(request, stage_id: int):
    """Прикрепляет документ к этапу-черновику."""
    return stub_action(request, 'Прикрепление документа')


@require_POST
@employee_required
def remove_document_view(request, document_id: int):
    """Открепляет документ от этапа-черновика."""
    return stub_action(request, 'Удаление документа')


@require_POST
@employee_required
def delete_draft_view(request, shipment_id: int):
    """Удаляет черновик перевозки целиком."""
    return stub_action(request, 'Удаление черновика')

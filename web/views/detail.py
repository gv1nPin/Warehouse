import logging

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from warehouse.common import PermissionName, StatusName
from warehouse.common.dto import StageDocumentDTO, StageDTO

from ..auth import employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http, business_errors_as_messages, redirect_back
from ..services import dispatch_service, route_service
from ..uploads import open_stage_file
from .draft import draft_panel_context

CANCELLABLE = (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)


def _is_mine(request, stage: StageDTO) -> bool:
    """Этап уходит со склада сотрудника, либо сотрудник — администратор."""
    return (
        stage.from_warehouse.id == request.actor.warehouse_id
        or PermissionName.EMPLOYEE_MANAGE in request.actor.permissions
    )


def stage_flags(request, stage: StageDTO, documents: list[StageDocumentDTO]) -> dict:
    """Что показать в этапе по правам, складу и статусу; шаблон только проверяет флаги."""
    perms = request.actor.permissions
    can_create = PermissionName.SHIPMENT_CREATE in perms
    can_dispatch = PermissionName.SHIPMENT_DISPATCH in perms
    mine = _is_mine(request, stage)
    status = stage.status_name
    first_draft = mine and stage.stage_order == 1 and status == StatusName.DRAFT
    return {
        'panel': can_create and first_draft,
        'reserve': can_dispatch and first_draft,
        'reserve_disabled': not documents,
        'reserve_hint': 'Сначала прикрепите документ' if can_create else 'Нужен документ: его прикрепляет старший кладовщик',
        'ship': can_dispatch and mine and status == StatusName.RESERVED,
        'driver_form': can_create and mine and status in (StatusName.WAITING, StatusName.RESERVED),
        'incoming': (
            PermissionName.SHIPMENT_ACCEPT in perms
            and status == StatusName.SHIPPED
            and stage.to_warehouse.id == request.actor.warehouse_id
        ),
        'waiting': status == StatusName.WAITING,
        'cancelled': status == StatusName.CANCELLED,
        'discrepancy': status == StatusName.DISCREPANCY,
        'show_fact': status in (StatusName.RECEIVED, StatusName.DISCREPANCY),
        'has_comments': any(item.comment for item in stage.items),
    }


@require_GET
@employee_required
@business_errors_as_http
@logged
def shipment_detail_view(request, shipment_id: int):
    """Карточка перевозки: маршрут, этапы с товарами и документами, кнопки действий."""
    employee_id = request.actor.employee_id
    perms = request.actor.permissions
    shipment = route_service().get_shipment_progress(employee_id, shipment_id)
    stages = []
    for stage in shipment.stages:
        documents = [] if stage.status_name == StatusName.WAITING else route_service().list_documents(employee_id, stage.id)
        stages.append({'stage': stage, 'documents': documents, 'flags': stage_flags(request, stage, documents)})
    first = shipment.stages[0]
    return render(request, 'web/detail/detail.html', {
        'shipment': shipment,
        'stages': stages,
        'route': [first.from_warehouse, *(stage.to_warehouse for stage in shipment.stages)],
        'my_warehouse_id': request.actor.warehouse_id,
        'panel': draft_panel_context(request, shipment),
        'can_cancel': (
            PermissionName.SHIPMENT_CANCEL in perms
            and all(stage.status_name in CANCELLABLE for stage in shipment.stages)
        ),
        'can_delete': (
            PermissionName.SHIPMENT_CREATE in perms
            and shipment.status_name == StatusName.DRAFT
            and _is_mine(request, first)
        ),
    })


@require_POST
@employee_required
@business_errors_as_messages
@logged
def reserve_view(request, stage_id: int):
    """Резервирует товар этапа на складе отправления."""
    stage = dispatch_service().reserve_stage(request.actor.employee_id, stage_id)
    messages.success(request, f'Этап зарезервирован: товар в резерве склада «{stage.from_warehouse.title}»')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def ship_view(request, stage_id: int):
    """Отправляет зарезервированный этап и списывает товар со склада."""
    dispatch_service().ship_stage(request.actor.employee_id, stage_id)
    messages.success(request, 'Этап отправлен: товар списан со склада')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def cancel_view(request, shipment_id: int):
    """Отменяет перевозку до отправки и возвращает резерв."""
    dispatch_service().cancel_shipment(request.actor.employee_id, shipment_id)
    messages.success(request, f'Перевозка №{shipment_id} отменена')
    return redirect_back(request)


@require_GET
@employee_required
@business_errors_as_http
@logged
def document_open_view(request, stage_id: int, document_id: int):
    """Открывает файл документа этапа в браузере; права проверяет list_documents."""
    documents = route_service().list_documents(request.actor.employee_id, stage_id)
    document = next((d for d in documents if d.id == document_id), None)
    if document is None:
        raise Http404('Документ не найден')
    try:
        file = open_stage_file(document.storage_path)
    except FileNotFoundError:
        logging.warning(
            'Файл документа №%s этапа №%s не найден на диске: %s', document_id, stage_id, document.storage_path
        )
        raise Http404('Файл документа не найден') from None
    return FileResponse(file, filename=document.file_name, as_attachment=False)

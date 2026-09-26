from datetime import date, timedelta

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from warehouse.common import PermissionName, StatusName
from warehouse.common.dto import NewStageDocument, NewStageItem, ShipmentDTO
from warehouse.common.exceptions import BusinessError, ValidationError

from ..auth import can, employee_required
from ..controller_logging import logged
from ..errors import business_errors_as_http, business_errors_as_messages, redirect_back
from ..services import draft_service, route_service
from ..uploads import delete_stage_file, save_stage_file

EDITABLE_STATUSES = (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)


def _number(raw: str | None) -> str:
    """Количество из поля ввода: запятая как точка, без пробелов; проверяет сервис."""
    return (raw or '').replace(',', '.').replace(' ', '').replace('\xa0', '').strip()


def _id(raw: str | None, error: str) -> int:
    """Номер из поля формы или ValidationError с понятным текстом."""
    raw = (raw or '').strip()
    if not raw.isdigit():
        raise ValidationError(error)
    return int(raw)


def _driver_id(raw: str | None) -> int | None:
    """Водитель из списка; пустое значение — без водителя."""
    return _id(raw, 'Выберите водителя из списка') if (raw or '').strip() else None


def _form_options(request) -> dict:
    """Склады, товары с доступным остатком и водители для формы создания."""
    service = draft_service()
    employee_id = request.actor.employee_id
    warehouses = service.list_warehouses(employee_id)
    return {
        'warehouses': warehouses,
        'my_warehouse_id': request.actor.warehouse_id,
        'my_warehouse': next((w for w in warehouses if w.id == request.actor.warehouse_id), None),
        'stock': service.list_available_stock(employee_id),
        'drivers': service.list_drivers(employee_id),
        'min_date': timezone.localdate().isoformat(),
    }


def _empty_form(options: dict) -> dict:
    """Значения по умолчанию: завтра, один следующий склад, одна пустая строка товара."""
    others = [w.id for w in options['warehouses'] if w.id != options['my_warehouse_id']]
    return {
        'planned_date': (timezone.localdate() + timedelta(days=1)).isoformat(),
        'route': [str(others[0]) if others else ''],
        'driver_id': '',
        'items': [('', '')],
    }


def _posted_form(request) -> dict:
    """Всё, что ввёл сотрудник, — чтобы вернуть в форму при ошибке."""
    post = request.POST
    items = list(zip(post.getlist('product_id'), post.getlist('quantity')))
    return {
        'planned_date': post.get('planned_date', ''),
        'route': post.getlist('route')[1:],
        'driver_id': post.get('driver_id', ''),
        'items': items or [('', '')],
    }


def _parse_date(raw: str) -> date:
    """Плановая дата из поля type=date."""
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise ValidationError('Укажите плановую дату') from None


def draft_panel_context(request, shipment: ShipmentDTO) -> dict:
    """Водители и остатки для панели черновика; пусто без shipment:create или без этапов в работе."""
    if not can(request, PermissionName.SHIPMENT_CREATE):
        return {}
    if not any(stage.status_name in EDITABLE_STATUSES for stage in shipment.stages):
        return {}
    service = draft_service()
    employee_id = request.actor.employee_id
    return {'drivers': service.list_drivers(employee_id), 'stock': service.list_available_stock(employee_id)}


@require_http_methods(['GET', 'POST'])
@employee_required
@business_errors_as_http
@logged
def draft_create_view(request):
    """Форма новой перевозки: создаёт черновик и возвращает к форме при ошибке."""
    options = _form_options(request)
    if request.method == 'GET':
        return render(request, 'web/draft/create.html', {**options, 'form': _empty_form(options)})

    form = _posted_form(request)
    files = request.FILES.getlist('documents')
    documents: list[NewStageDocument] = []
    try:
        planned_date = _parse_date(form['planned_date'])
        route = [_id(w, 'Выберите склады маршрута') for w in request.POST.getlist('route')]
        items = [
            NewStageItem(product_id=_id(product, 'Выберите товар из списка'), quantity=_number(quantity))
            for product, quantity in form['items']
            if product.strip()
        ]
        for f in files:
            documents.append(save_stage_file(f))
        shipment = draft_service().create_draft(
            request.actor.employee_id,
            planned_date,
            route,
            items,
            driver_id=_driver_id(form['driver_id']),
            documents=documents,
        )
    except BusinessError as exc:
        for document in documents:
            delete_stage_file(document.storage_path)
        return render(request, 'web/draft/create.html', {
            **options, 'form': form, 'error': exc.message, 'files_lost': bool(files),
        })

    suffix = '' if documents else ': прикрепите документ перед резервом'
    messages.success(request, f'Черновик №{shipment.id} создан{suffix}')
    return redirect('shipment_detail', shipment_id=shipment.id)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def add_item_view(request, stage_id: int):
    """Добавляет товар в этап-черновик или меняет его количество."""
    product_id = _id(request.POST.get('product_id'), 'Выберите товар из списка')
    draft_service().add_item(request.actor.employee_id, stage_id, product_id, _number(request.POST.get('quantity')))
    messages.success(request, 'Товар добавлен')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def remove_item_view(request, item_id: int):
    """Убирает позицию из этапа-черновика."""
    draft_service().remove_item(request.actor.employee_id, item_id)
    messages.success(request, 'Позиция убрана')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def assign_driver_view(request, stage_id: int):
    """Назначает или снимает водителя этапа."""
    driver_id = _driver_id(request.POST.get('driver_id'))
    draft_service().assign_driver(request.actor.employee_id, stage_id, driver_id)
    messages.success(request, 'Водитель назначен' if driver_id else 'Водитель снят')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def attach_document_view(request, stage_id: int):
    """Сохраняет выбранные файлы и прикрепляет их к этапу-черновику."""
    files = request.FILES.getlist('documents')
    if not files:
        raise ValidationError('Выберите файл')
    attached = 0
    for f in files:
        try:
            document = save_stage_file(f)
        except ValidationError as exc:
            messages.error(request, exc.message)
            continue
        try:
            draft_service().attach_document(request.actor.employee_id, stage_id, document)
        except BusinessError:
            delete_stage_file(document.storage_path)
            raise
        attached += 1
    if attached:
        messages.success(request, f'Прикреплено документов: {attached}')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def remove_document_view(request, document_id: int):
    """Открепляет документ и удаляет его файл с диска."""
    document = draft_service().remove_document(request.actor.employee_id, document_id)
    delete_stage_file(document.storage_path)
    messages.success(request, 'Документ откреплён')
    return redirect_back(request)


@require_POST
@employee_required
@business_errors_as_messages
@logged
def delete_draft_view(request, shipment_id: int):
    """Удаляет черновик целиком вместе с файлами документов."""
    employee_id = request.actor.employee_id
    shipment = route_service().get_shipment_progress(employee_id, shipment_id)
    documents = route_service().list_documents(employee_id, shipment.stages[0].id)
    draft_service().delete_draft(employee_id, shipment_id)
    for document in documents:
        delete_stage_file(document.storage_path)
    messages.success(request, f'Черновик №{shipment_id} удалён')
    return redirect('shipments')

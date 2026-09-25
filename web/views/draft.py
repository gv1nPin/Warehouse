<<<<<<< HEAD
"""Черновик: создание, товары, водитель, документы, удаление."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from warehouse.common import PermissionName
from warehouse.common.dto import NewStageDocument, NewStageItem
from warehouse.common.exceptions import BusinessError

from ..auth import can, employee_required
from ..services import draft_service
from ..uploads import save_stage_file, delete_stage_file
from ._helpers import bll_call, bll_err, bll_ok, eid


def _require_create(request):
    if not can(request, PermissionName.SHIPMENT_CREATE):
        messages.error(request, "Недостаточно прав для работы с черновиком")
        return False
    return True


@require_http_methods(["GET", "POST"])
@employee_required
def draft_create_view(request):
    """Форма новой перевозки → create_draft."""
    if not _require_create(request):
        return redirect("home")

    employee_id = eid(request)
    svc = draft_service()

    try:
        warehouses = svc.list_warehouses(employee_id)
        stock = svc.list_available_stock(employee_id)
        drivers = svc.list_drivers(employee_id)
    except BusinessError as exc:
        messages.error(request, getattr(exc, "message", str(exc)))
        warehouses, stock, drivers = [], [], []

    if request.method == "GET":
        return render(
            request,
            "web/pages/shipment_create.html",
            {
                "our_warehouse": {
                    "title": request.session.get("warehouse_title") or "Склад",
                    "address": "",
                },
                "warehouses": warehouses,
                "drivers": drivers,
                "products": stock,
                "route_steps": [w.id for w in warehouses[:1]] if warehouses else [],
                "items": [],
                "planned_date": date.today().isoformat(),
                "min_date": date.today().isoformat(),
                "driver_id": "",
                "summary_route": request.session.get("warehouse_title") or "ваш склад",
                "summary_stages": 1,
                "error": None,
            },
        )

    # POST create
    planned_raw = request.POST.get("planned_date") or ""
    try:
        y, m, d = planned_raw.split("-")
        planned = date(int(y), int(m), int(d))
    except ValueError:
        messages.error(request, "Некорректная плановая дата")
        return redirect("draft_new")

    our = getattr(request.actor, "warehouse_id", None)
    route_wh = [int(x) for x in request.POST.getlist("route_wh") if x]
    route = ([our] if our else []) + route_wh

    products = request.POST.getlist("item_product")
    qtys = request.POST.getlist("item_qty")
    items: list[NewStageItem] = []
    for pid, q in zip(products, qtys):
        try:
            items.append(NewStageItem(product_id=int(pid), quantity=Decimal(str(q).replace(",", "."))))
        except (ValueError, InvalidOperation):
            continue

    driver_raw = request.POST.get("driver_id") or None
    driver_id = int(driver_raw) if driver_raw else None

    documents: list[NewStageDocument] = []
    for f in request.FILES.getlist("documents"):
        try:
            documents.append(save_stage_file(f, )
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Файл «{f.name}»: {exc}")

    try:
        bll_call(
            "ShipmentDraftService.create_draft",
            request,
            planned_date=str(planned),
            route=route,
            items=items,
            driver_id=driver_id,
            documents=documents,
        )
        shipment = svc.create_draft(
            employee_id=employee_id,
            planned_date=planned,
            route=route,
            items=items,
            driver_id=driver_id,
            documents=documents,
        )
        bll_ok("ShipmentDraftService.create_draft", shipment)
        sid = getattr(shipment, "id", None)
        messages.success(request, f"Черновик №{sid} создан")
        if sid:
            return redirect("shipment_detail", shipment_id=sid)
        return redirect("shipments")
    except BusinessError as exc:
        bll_err("ShipmentDraftService.create_draft", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
        return redirect("draft_new")
=======
from django.views.decorators.http import require_http_methods, require_POST

from ..auth import employee_required
from ._stub import stub_action, stub_page


@require_http_methods(['GET', 'POST'])
@employee_required
def draft_create_view(request):
    """Форма создания черновика перевозки."""
    return stub_page(request, 'Новая перевозка')
>>>>>>> main


@require_POST
@employee_required
def add_item_view(request, stage_id: int):
<<<<<<< HEAD
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    try:
        product_id = int(request.POST.get("product_id"))
        quantity = Decimal(str(request.POST.get("quantity", "1")).replace(",", "."))
        bll_call(
            "ShipmentDraftService.add_item",
            request,
            stage_id=stage_id,
            product_id=product_id,
            quantity=str(quantity),
        )
        draft_service().add_item(employee_id, stage_id, product_id=product_id, quantity=quantity)
        bll_ok("ShipmentDraftService.add_item")
        messages.success(request, "Товар добавлен")
    except (BusinessError, ValueError, InvalidOperation) as exc:
        bll_err("ShipmentDraftService.add_item", request, exc if isinstance(exc, Exception) else Exception(str(exc)))
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Добавляет товар в этап-черновик."""
    return stub_action(request, 'Добавление товара')
>>>>>>> main


@require_POST
@employee_required
def remove_item_view(request, item_id: int):
<<<<<<< HEAD
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    try:
        bll_call("ShipmentDraftService.remove_item", request, item_id=item_id)
        draft_service().remove_item(employee_id, item_id)
        bll_ok("ShipmentDraftService.remove_item")
        messages.success(request, "Товар убран")
    except BusinessError as exc:
        bll_err("ShipmentDraftService.remove_item", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Убирает товар из этапа-черновика."""
    return stub_action(request, 'Удаление товара')
>>>>>>> main


@require_POST
@employee_required
def assign_driver_view(request, stage_id: int):
<<<<<<< HEAD
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    raw = request.POST.get("driver_id") or ""
    driver_id = int(raw) if raw else None
    try:
        bll_call("ShipmentDraftService.assign_driver", request, stage_id=stage_id, driver_id=driver_id)
        draft_service().assign_driver(employee_id, stage_id, driver_id)
        bll_ok("ShipmentDraftService.assign_driver")
        messages.success(request, "Водитель назначен" if driver_id else "Водитель снят")
    except BusinessError as exc:
        bll_err("ShipmentDraftService.assign_driver", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Назначает или снимает водителя этапа."""
    return stub_action(request, 'Назначение водителя')
>>>>>>> main


@require_POST
@employee_required
def attach_document_view(request, stage_id: int):
<<<<<<< HEAD
    """Web сохраняет файл → NewStageDocument → draft.attach_document."""
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    files = request.FILES.getlist("document") or request.FILES.getlist("documents")
    if not files:
        messages.error(request, "Файл не выбран")
        return redirect(request.META.get("HTTP_REFERER") or "shipments")

    attached = 0
    for f in files:
        try:
            doc = save_stage_file(f)
            bll_call(
                "ShipmentDraftService.attach_document",
                request,
                stage_id=stage_id,
                document=doc,
            )
            draft_service().attach_document(employee_id, stage_id, doc)
            bll_ok("ShipmentDraftService.attach_document")
            attached += 1
        except BusinessError as exc:
            bll_err("ShipmentDraftService.attach_document", request, exc)
            messages.error(request, getattr(exc, "message", str(exc)))
        except Exception as exc:  # noqa: BLE001
            bll_err("ShipmentDraftService.attach_document", request, exc)
            messages.error(request, f"«{getattr(f, 'name', 'file')}»: {exc}")

    if attached:
        messages.success(
            request,
            f"Прикреплено документов: {attached}" if attached > 1 else f"Документ «{files[0].name}» прикреплён",
        )
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Прикрепляет документ к этапу-черновику."""
    return stub_action(request, 'Прикрепление документа')
>>>>>>> main


@require_POST
@employee_required
def remove_document_view(request, document_id: int):
<<<<<<< HEAD
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    storage_path = (request.POST.get("storage_path") or "").strip()
    try:
        bll_call("ShipmentDraftService.remove_document", request, document_id=document_id)
        draft_service().remove_document(employee_id, document_id)
        delete_stage_file(storage_path)
        bll_ok("ShipmentDraftService.remove_document", document_id=document_id)
        messages.success(request, "Документ откреплён")
    except BusinessError as exc:
        bll_err("ShipmentDraftService.remove_document", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Открепляет документ от этапа-черновика."""
    return stub_action(request, 'Удаление документа')
>>>>>>> main


@require_POST
@employee_required
def delete_draft_view(request, shipment_id: int):
<<<<<<< HEAD
    if not _require_create(request):
        return redirect("home")
    employee_id = eid(request)
    try:
        bll_call("ShipmentDraftService.delete_draft", request, shipment_id=shipment_id)
        draft_service().delete_draft(employee_id, shipment_id)
        bll_ok("ShipmentDraftService.delete_draft", shipment_id=shipment_id)
        messages.success(request, f"Черновик №{shipment_id} удалён")
    except BusinessError as exc:
        bll_err("ShipmentDraftService.delete_draft", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect("shipments")
=======
    """Удаляет черновик перевозки целиком."""
    return stub_action(request, 'Удаление черновика')
>>>>>>> main

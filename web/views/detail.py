<<<<<<< HEAD
"""Карточка перевозки, резерв, отправка, отмена, документ."""
from __future__ import annotations

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import BusinessError

from ..auth import can, employee_required
from ..services import dispatch_service, route_service
from ..status_ui import status_css, status_label
from ._helpers import bll_call, bll_err, bll_ok, eid
=======
from django.views.decorators.http import require_GET, require_POST

from ..auth import employee_required
from ._stub import stub_action, stub_page
>>>>>>> main


@require_GET
@employee_required
def shipment_detail_view(request, shipment_id: int):
    """Карточка перевозки со всеми этапами."""
<<<<<<< HEAD
    employee_id = eid(request)
    try:
        bll_call("RouteQueryService.get_shipment_progress", request, shipment_id=shipment_id)
        shipment = route_service().get_shipment_progress(employee_id, shipment_id)
        bll_ok("RouteQueryService.get_shipment_progress", shipment)
    except BusinessError as exc:
        bll_err("RouteQueryService.get_shipment_progress", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
        return redirect("shipments")

    status = getattr(shipment, "status_name", "") or ""
    planned = getattr(shipment, "planned_date", "") or ""
    if hasattr(planned, "strftime"):
        planned = planned.strftime("%d.%m.%Y")

    raw_stages = getattr(shipment, "stages", None) or ()
    route_nodes = []
    our_wh = getattr(request.actor, "warehouse_id", None)
    seen = []
    for stg in raw_stages:
        for wh in (getattr(stg, "from_warehouse", None), getattr(stg, "to_warehouse", None)):
            if wh is None:
                continue
            wid = getattr(wh, "id", None)
            if wid in seen:
                continue
            seen.append(wid)
            route_nodes.append(
                {
                    "title": getattr(wh, "title", ""),
                    "city": getattr(wh, "address", "") or "",
                    "mine": our_wh is not None and wid == our_wh,
                }
            )

    stages_out = []
    for i, stg in enumerate(raw_stages):
        st = getattr(stg, "status_name", "") or ""
        items = []
        has_comments = False
        for it in getattr(stg, "items", None) or ():
            qty_doc = getattr(it, "document_quantity", None)
            qty_fact = getattr(it, "actual_quantity", None)
            comment = getattr(it, "comment", None) or ""
            if comment:
                has_comments = True
            items.append(
                {
                    "id": getattr(it, "id", None),
                    "product_id": getattr(it, "product_id", None),
                    "article": getattr(it, "article_number", "") or "",
                    "name": getattr(it, "product_name", "") or "",
                    "unit": getattr(it, "measurement_name", "") or "",
                    "qty_doc": qty_doc,
                    "qty_fact": qty_fact,
                    "comment": comment,
                    "diff": qty_fact is not None and qty_doc is not None and qty_fact != qty_doc,
                }
            )

        docs = []
        # документы подгружаются отдельно при необходимости; в progress могут отсутствовать
        stage_id = getattr(stg, "id", None)
        if stage_id:
            try:
                for d in route_service().list_documents(employee_id, stage_id):
                    name = getattr(d, "file_name", "file")
                    ext = (name.rsplit(".", 1)[-1] if "." in name else "").upper()[:4]
                    size_b = getattr(d, "size_bytes", None)
                    size_label = ""
                    if size_b is not None:
                        size_label = (
                            f"{max(1, round(size_b / 1024))} КБ"
                            if size_b < 1048576
                            else f"{size_b / 1048576:.1f} МБ".replace(".", ",")
                        )
                    docs.append(
                        {
                            "id": getattr(d, "id", None),
                            "name": name,
                            "ext": ext,
                            "size": size_label,
                            "by": getattr(d, "uploaded_by_name", "") or "",
                            "at": getattr(d, "uploaded_at", "") or "",
                            "storage_path": getattr(d, "storage_path", "") or "",
                        }
                    )
            except BusinessError:
                pass

        from_wh = getattr(stg, "from_warehouse", None)
        to_wh = getattr(stg, "to_warehouse", None)
        stages_out.append(
            {
                "id": stage_id,
                "index": getattr(stg, "stage_order", i + 1),
                "from_name": getattr(from_wh, "title", "") if from_wh else "",
                "to_name": getattr(to_wh, "title", "") if to_wh else "",
                "status": status_css(st),
                "status_name": st,
                "status_label": status_label(st),
                "driver": getattr(stg, "driver_name", None),
                "shipped_at": getattr(stg, "sent_at", None),
                "items": items,
                "show_fact": st in (StatusName.RECEIVED, StatusName.DISCREPANCY),
                "has_comments": has_comments,
                "docs": docs,
                "has_docs": bool(docs),
                "can_attach": can(request, PermissionName.SHIPMENT_CREATE)
                and st == StatusName.DRAFT
                and i == 0,
                "can_reserve": can(request, PermissionName.SHIPMENT_DISPATCH)
                and st == StatusName.DRAFT
                and i == 0,
                "can_ship": can(request, PermissionName.SHIPMENT_DISPATCH) and st == StatusName.RESERVED,
                "can_go_receipt": can(request, PermissionName.SHIPMENT_ACCEPT)
                and st == StatusName.SHIPPED,
            }
        )

    cancellable = all(
        getattr(s, "status_name", "")
        in (StatusName.DRAFT, StatusName.WAITING, StatusName.RESERVED)
        for s in raw_stages
    ) if raw_stages else False

    return render(
        request,
        "web/pages/shipment_detail.html",
        {
            "shipment": {
                "id": shipment_id,
                "status": status_css(status),
                "status_label": status_label(status),
                "planned_date": planned,
                "creator": getattr(shipment, "creator_name", "") or "",
            },
            "route_nodes": route_nodes,
            "stages": stages_out,
            "can_cancel": can(request, PermissionName.SHIPMENT_CANCEL) and cancellable,
            "can_delete": can(request, PermissionName.SHIPMENT_CREATE) and status == StatusName.DRAFT,
        },
    )
=======
    return stub_page(request, f'Перевозка №{shipment_id}')
>>>>>>> main


@require_POST
@employee_required
def reserve_view(request, stage_id: int):
<<<<<<< HEAD
    employee_id = eid(request)
    try:
        bll_call("ShipmentDispatchService.reserve_stage", request, stage_id=stage_id)
        dto = dispatch_service().reserve_stage(employee_id=employee_id, stage_id=stage_id)
        bll_ok("ShipmentDispatchService.reserve_stage", dto)
        messages.success(request, "Этап зарезервирован")
    except BusinessError as exc:
        bll_err("ShipmentDispatchService.reserve_stage", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Резервирует товар этапа на складе отправления."""
    return stub_action(request, 'Резерв этапа')
>>>>>>> main


@require_POST
@employee_required
def ship_view(request, stage_id: int):
<<<<<<< HEAD
    employee_id = eid(request)
    try:
        bll_call("ShipmentDispatchService.ship_stage", request, stage_id=stage_id)
        dto = dispatch_service().ship_stage(employee_id=employee_id, stage_id=stage_id)
        bll_ok("ShipmentDispatchService.ship_stage", dto)
        messages.success(request, "Этап отправлен")
    except BusinessError as exc:
        bll_err("ShipmentDispatchService.ship_stage", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect(request.META.get("HTTP_REFERER") or "shipments")
=======
    """Отправляет этап со склада."""
    return stub_action(request, 'Отправка этапа')
>>>>>>> main


@require_POST
@employee_required
def cancel_view(request, shipment_id: int):
<<<<<<< HEAD
    employee_id = eid(request)
    try:
        bll_call("ShipmentDispatchService.cancel_shipment", request, shipment_id=shipment_id)
        dto = dispatch_service().cancel_shipment(employee_id=employee_id, shipment_id=shipment_id)
        bll_ok("ShipmentDispatchService.cancel_shipment", dto)
        messages.success(request, f"Перевозка №{shipment_id} отменена")
    except BusinessError as exc:
        bll_err("ShipmentDispatchService.cancel_shipment", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect("shipment_detail", shipment_id=shipment_id)
=======
    """Отменяет перевозку до отправки."""
    return stub_action(request, 'Отмена перевозки')
>>>>>>> main


@require_GET
@employee_required
def document_open_view(request, stage_id: int, document_id: int):
<<<<<<< HEAD
    """Отдаёт файл документа этапа с диска MEDIA."""
    from django.core.files.storage import default_storage

    employee_id = eid(request)
    try:
        docs = route_service().list_documents(employee_id, stage_id)
    except BusinessError as exc:
        messages.error(request, getattr(exc, "message", str(exc)))
        raise Http404 from exc

    doc = next((d for d in docs if getattr(d, "id", None) == document_id), None)
    if doc is None:
        raise Http404
    path = getattr(doc, "storage_path", "") or ""
    if not path or not default_storage.exists(path):
        raise Http404
    return FileResponse(default_storage.open(path, "rb"), filename=getattr(doc, "file_name", "file"))
=======
    """Отдаёт файл документа этапа."""
    return stub_page(request, 'Документ')
>>>>>>> main

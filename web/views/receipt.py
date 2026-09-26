"""Приёмка: входящие этапы, факт, accept."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import BusinessError

from ..auth import can, employee_required
from ..services import receipt_service
from ..status_ui import status_label
from ._helpers import bll_call, bll_err, bll_ok, eid


@require_GET
@employee_required
def receipt_list_view(request):
    if not can(request, PermissionName.SHIPMENT_ACCEPT):
        messages.error(request, "Недостаточно прав для приёмки")
        return redirect("home")

    employee_id = eid(request)
    try:
        bll_call("ShipmentReceiptService.get_incoming", request)
        stages = receipt_service().get_incoming(employee_id)
        bll_ok("ShipmentReceiptService.get_incoming", count=len(stages))
    except BusinessError as exc:
        bll_err("ShipmentReceiptService.get_incoming", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
        stages = []

    incoming = []
    for s in stages:
        if getattr(s, "status_name", "") != StatusName.SHIPPED:
            continue
        from_wh = getattr(s, "from_warehouse", None)
        to_wh = getattr(s, "to_warehouse", None)
        items = []
        for it in getattr(s, "items", None) or ():
            items.append(
                {
                    "id": getattr(it, "id", None),
                    "product_id": getattr(it, "product_id", None),
                    "article": getattr(it, "article_number", "") or "",
                    "name": getattr(it, "product_name", "") or "",
                    "unit": getattr(it, "measurement_name", "") or "",
                    "qty_doc": getattr(it, "document_quantity", None),
                }
            )
        incoming.append(
            {
                "id": getattr(s, "id", None),
                "shipment_id": getattr(s, "shipment_id", None),
                "index": getattr(s, "stage_order", 1),
                "stages_total": "",
                "from_name": getattr(from_wh, "title", "") if from_wh else "",
                "to_name": getattr(to_wh, "title", "") if to_wh else "",
                "driver": getattr(s, "driver_name", None),
                "shipped_at": getattr(s, "sent_at", None),
                "status_label": status_label(getattr(s, "status_name", "")),
                "items": items,
            }
        )

    return render(request, "web/pages/receipt.html", {"incoming": incoming})


@require_POST
@employee_required
def save_facts_view(request, stage_id: int):
    """enter_actual_quantity по всем fact_<item_id>."""
    if not can(request, PermissionName.SHIPMENT_ACCEPT):
        messages.error(request, "Недостаточно прав")
        return redirect("home")

    employee_id = eid(request)
    try:
        for key, val in request.POST.items():
            if not key.startswith("fact_"):
                continue
            item_id = int(key[5:])
            qty = Decimal(str(val).replace(",", ".").replace(" ", ""))
            comment = (request.POST.get(f"com_{item_id}") or "").strip() or None
            bll_call(
                "ShipmentReceiptService.enter_actual_quantity",
                request,
                item_id=item_id,
                quantity=str(qty),
                comment=comment,
            )
            receipt_service().enter_actual_quantity(
                employee_id=employee_id,
                item_id=item_id,
                quantity=qty,
                comment=comment,
            )
            bll_ok("ShipmentReceiptService.enter_actual_quantity", item_id=item_id)
        messages.success(request, "Факт сохранён")
    except (BusinessError, ValueError, InvalidOperation) as exc:
        bll_err(
            "ShipmentReceiptService.enter_actual_quantity",
            request,
            exc if isinstance(exc, Exception) else Exception(str(exc)),
        )
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect("receipt")


@require_POST
@employee_required
def accept_view(request, stage_id: int):
    """Сначала факты (если пришли в POST), затем accept_stage."""
    if not can(request, PermissionName.SHIPMENT_ACCEPT):
        messages.error(request, "Недостаточно прав")
        return redirect("home")

    employee_id = eid(request)
    try:
        for key, val in request.POST.items():
            if not key.startswith("fact_"):
                continue
            item_id = int(key[5:])
            qty = Decimal(str(val).replace(",", ".").replace(" ", ""))
            comment = (request.POST.get(f"com_{item_id}") or "").strip() or None
            receipt_service().enter_actual_quantity(
                employee_id=employee_id,
                item_id=item_id,
                quantity=qty,
                comment=comment,
            )
        bll_call("ShipmentReceiptService.accept_stage", request, stage_id=stage_id)
        dto = receipt_service().accept_stage(employee_id=employee_id, stage_id=stage_id)
        bll_ok("ShipmentReceiptService.accept_stage", dto)
        messages.success(request, "Этап принят")
    except (BusinessError, ValueError, InvalidOperation) as exc:
        bll_err(
            "ShipmentReceiptService.accept_stage",
            request,
            exc if isinstance(exc, Exception) else Exception(str(exc)),
        )
        messages.error(request, getattr(exc, "message", str(exc)))
    return redirect("receipt")

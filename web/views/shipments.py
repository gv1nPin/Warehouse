"""Список перевозок / рейсов."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import render
from django.views.decorators.http import require_GET

from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import BusinessError

from ..auth import can, employee_required
from ..services import route_service
from ..status_ui import STATUS_FILTERS, normalize_status_query, status_css, status_label
from ._helpers import bll_call, bll_err, bll_ok, eid


@require_GET
@employee_required
def shipment_list_view(request):
    """Список этапов с фильтром status и поиском q."""
    employee_id = eid(request)
    q = (request.GET.get("q") or "").strip()
    status_filter = normalize_status_query(request.GET.get("status") or "all")
    trips_only = request.GET.get("trips") == "1"

    try:
        bll_call("RouteQueryService.list_routes", request, only_active=False)
        stages = route_service().list_routes(employee_id, only_active=False)
        bll_ok("RouteQueryService.list_routes", count=len(stages))
    except BusinessError as exc:
        bll_err("RouteQueryService.list_routes", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
        stages = []

    me = request.session.get("employee_name", "")
    rows = []
    for s in stages:
        st = getattr(s, "status_name", "") or ""
        if status_filter != "all" and st != status_filter:
            continue
        driver = getattr(s, "driver_name", None)
        if trips_only:
            if not me or me not in (driver or ""):
                continue

        from_wh = getattr(s, "from_warehouse", None)
        to_wh = getattr(s, "to_warehouse", None)
        from_name = getattr(from_wh, "title", None) or "—"
        to_name = getattr(to_wh, "title", None) or "—"
        planned = getattr(s, "planned_date", None) or ""
        if hasattr(planned, "strftime"):
            planned = planned.strftime("%d.%m.%Y")

        shipment_id = getattr(s, "shipment_id", None)
        if q:
            blob = " ".join(
                str(x).lower()
                for x in (shipment_id, st, status_label(st), driver, from_name, to_name)
            )
            if q.lower().lstrip("№") not in blob and q.lower() not in blob:
                continue

        rows.append(
            {
                "shipment_id": shipment_id,
                "stage_index": getattr(s, "stage_order", 1),
                "stages_total": "",
                "from_name": from_name,
                "to_name": to_name,
                "dir": "out",
                "planned_date": planned,
                "driver": driver,
                "creator": "",
                "stage_status": status_css(st),
                "stage_status_label": status_label(st),
            }
        )

    view_all = can(request, PermissionName.SHIPMENT_VIEW_ALL)
    return render(
        request,
        "web/pages/shipment_list.html",
        {
            "page_title": "Мои рейсы" if trips_only else ("Все перевозки" if view_all else "Перевозки"),
            "page_sub": (
                "Этапы, где вы назначены водителем"
                if trips_only
                else ("Перевозки всех складов" if view_all else "Исходящие и входящие этапы вашего склада")
            ),
            "can_create": can(request, PermissionName.SHIPMENT_CREATE) and not trips_only,
            "trips_only": trips_only,
            "q": q,
            "status_filter": status_filter,
            "status_filters": STATUS_FILTERS,
            "rows": rows,
        },
    )

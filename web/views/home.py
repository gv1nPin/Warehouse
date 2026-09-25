"""Главная и остатки."""
from __future__ import annotations

from decimal import Decimal

from django.contrib import messages
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from warehouse.common import PermissionName, StatusName
from warehouse.common.exceptions import BusinessError

from ..auth import employee_required
from ..services import draft_service, route_service
from ..status_ui import status_css
from ._helpers import bll_call, bll_err, bll_ok, eid, has_perm, home_layout


@require_GET
@employee_required
def home_view(request):
    """Главная: счётчики и плитки по permissions из БД."""
    layout = home_layout(request)
    employee_id = eid(request)

    try:
        bll_call("RouteQueryService.list_routes", request, only_active=False)
        stages = route_service().list_routes(employee_id, only_active=False)
        bll_ok("RouteQueryService.list_routes", count=len(stages))
    except BusinessError as exc:
        bll_err("RouteQueryService.list_routes", request, exc)
        stages = []
        messages.error(request, getattr(exc, "message", str(exc)))

    def count_status(name: StatusName) -> int:
        return sum(1 for s in stages if getattr(s, "status_name", "") == name)

    me = request.session.get("employee_name", "")

    def count_trips() -> int:
        return sum(
            1
            for s in stages
            if getattr(s, "status_name", "") == StatusName.RESERVED
            and me
            and me in (getattr(s, "driver_name", None) or "")
        )

    counter_meta = {
        "draft": {
            "t": "Черновики",
            "h": "Ещё не зарезервированы",
            "st": status_css(StatusName.DRAFT),
            "n": count_status(StatusName.DRAFT),
            "url": reverse("shipments") + f"?status={StatusName.DRAFT}",
        },
        "reserved": {
            "t": "Ждут отправки",
            "h": "Товар в резерве",
            "st": status_css(StatusName.RESERVED),
            "n": count_status(StatusName.RESERVED),
            "url": reverse("shipments") + f"?status={StatusName.RESERVED}",
        },
        "incoming": {
            "t": "Едет к вам",
            "h": "Отправлено на ваш склад",
            "st": status_css(StatusName.SHIPPED),
            "n": count_status(StatusName.SHIPPED),
            "url": reverse("receipt"),
        },
        "discrepancy": {
            "t": "Расхождения",
            "h": "Факт не совпал с документом",
            "st": status_css(StatusName.DISCREPANCY),
            "n": count_status(StatusName.DISCREPANCY),
            "url": reverse("shipments") + f"?status={StatusName.DISCREPANCY}",
        },
        "trips": {
            "t": "Предстоящие рейсы",
            "h": "Зарезервированы, ждут отправки",
            "st": status_css(StatusName.RESERVED),
            "n": count_trips(),
            "url": reverse("shipments") + "?trips=1",
        },
    }

    tile_meta = {
        "create": {
            "t": "Создать перевозку",
            "d": "Маршрут, товары, водитель, документы",
            "url": reverse("draft_new"),
        },
        "shipments": {
            "t": "Посмотреть перевозки",
            "d": "Исходящие и входящие этапы склада",
            "url": reverse("shipments"),
        },
        "receipt": {
            "t": "Приёмка",
            "d": "Ввод факта и приёмка этапов",
            "url": reverse("receipt"),
        },
        "stock": {
            "t": "Остатки",
            "d": "На складе, в резерве, доступно",
            "url": reverse("stock"),
        },
        "docs": {
            "t": "Документы",
            "d": "Накладные, акты, фото",
            "url": reverse("shipments"),
        },
        "employees": {
            "t": "Сотрудники",
            "d": "Регистрация и блокировка",
            "url": reverse("employee_new"),
        },
        "refs": {
            "t": "Справочники",
            "d": "Товары, склады, единицы",
            "url": reverse("home"),
        },
        "trips": {
            "t": "Мои рейсы",
            "d": "Этапы, где вы водитель",
            "url": reverse("shipments") + "?trips=1",
        },
    }

    return render(
        request,
        "web/pages/home.html",
        {
            "counters": [counter_meta[k] for k in layout["counters"] if k in counter_meta],
            "main_tiles": [tile_meta[k] for k in layout["main"] if k in tile_meta],
            "extra_tiles": [tile_meta[k] for k in layout["extra"] if k in tile_meta],
        },
    )


@require_GET
@employee_required
def stock_view(request):
    """Остатки склада сотрудника (list_available_stock)."""
    q = (request.GET.get("q") or "").strip().lower()
    employee_id = eid(request)
    try:
        bll_call("ShipmentDraftService.list_available_stock", request)
        stocks = draft_service().list_available_stock(employee_id)
        bll_ok("ShipmentDraftService.list_available_stock", count=len(stocks))
    except BusinessError as exc:
        bll_err("ShipmentDraftService.list_available_stock", request, exc)
        messages.error(request, getattr(exc, "message", str(exc)))
        stocks = []

    rows = []
    for s in stocks:
        article = getattr(s, "article_number", "") or ""
        name = getattr(s, "product_name", "") or ""
        if q and q not in article.lower() and q not in name.lower():
            continue
        qty = getattr(s, "quantity", Decimal(0))
        reserved = getattr(s, "reserved_quantity", Decimal(0))
        available = getattr(s, "available", qty - reserved)
        rows.append(
            {
                "article": article,
                "name": name,
                "unit": getattr(s, "measurement_name", ""),
                "qty": qty,
                "reserved": reserved,
                "available": available,
            }
        )

    return render(
        request,
        "web/pages/stock.html",
        {
            "warehouse_label": request.session.get("warehouse_title") or "Ваш склад",
            "q": request.GET.get("q") or "",
            "rows": rows,
            "can_manage": has_perm(request, PermissionName.EMPLOYEE_MANAGE),
        },
    )

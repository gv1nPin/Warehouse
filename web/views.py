"""
Серверный рендер страниц кабинета (вместо SPA index.html).

Логика JS из прототипа намеренно не переносится: каждое действие —
отдельный HTTP-запрос (GET страница / POST форма), view вызывает BLL.
"""
from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from dependency_injector.wiring import Provide, inject
from container import Container

from warehouse.bll.services.auth_service import LoginService
from warehouse.bll.services.shipment_service import (
    RouteQueryService,
    ShipmentDispatchService,
    ShipmentDraftService,
    ShipmentReceiptService,
)
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from warehouse.common.dto import NewStageDocument, NewStageItem
from warehouse.common.exceptions import BusinessError

# Логирование границы web → DTO → BLL
try:
    from controller_logging import (  # когда файл лежит рядом с views
        log_bll_call,
        log_bll_ok,
        log_bll_error,
        dto_preview,
    )
except ImportError:
    from .controller_logging import (  # package-style: web.controller_logging
        log_bll_call,
        log_bll_ok,
        log_bll_error,
        dto_preview,
    )
import logging
_log = logging.getLogger("web.controllers")


STATUS_LABELS = {
    "draft": "Черновик",
    "waiting": "В ожидании",
    "reserved": "Зарезервировано",
    "shipped": "Отправлено",
    "received": "Принято",
    "discrepancy": "Принято с расхождениями",
    "cancelled": "Отменено",
}

STATUS_FILTERS = [
    ("all", "Все"),
    ("draft", "Черновик"),
    ("reserved", "Зарезервировано"),
    ("shipped", "Отправлено"),
    ("discrepancy", "С расхождениями"),
    ("received", "Принято"),
    ("cancelled", "Отменено"),
]

# Права по ролям — зеркало RolePermissions / прототипа
ROLE_PERMS: dict[str, set[str]] = {
    "senior": {"create", "dispatch", "accept"},
    "keeper": {"dispatch", "accept"},
    "manager": {"cancel", "view_all"},
    "admin": {"create", "dispatch", "accept", "cancel", "view_all", "manage"},
    "driver": set(),
}

ROLE_HOME: dict[str, dict[str, list[str]]] = {
    "senior": {
        "counters": ["draft", "reserved", "incoming", "discrepancy"],
        "main": ["create", "shipments"],
        "extra": ["receipt", "stock", "docs"],
    },
    "keeper": {
        "counters": ["reserved", "incoming"],
        "main": ["shipments", "receipt"],
        "extra": ["stock", "docs"],
    },
    "manager": {
        "counters": ["draft", "reserved", "discrepancy"],
        "main": ["shipments"],
        "extra": ["docs"],
    },
    "admin": {
        "counters": ["draft", "reserved", "incoming", "discrepancy"],
        "main": ["create", "shipments"],
        "extra": ["receipt", "stock", "docs", "employees", "refs"],
    },
    "driver": {
        "counters": ["trips"],
        "main": ["trips"],
        "extra": [],
    },
}


def _role_key(role_name: str | None) -> str:
    if not role_name:
        return "keeper"
    n = role_name.lower()
    mapping = {
        "старший кладовщик": "senior",
        "кладовщик": "keeper",
        "менеджер": "manager",
        "администратор": "admin",
        "администратор системы": "admin",
        "водитель": "driver",
        "senior": "senior",
        "keeper": "keeper",
        "manager": "manager",
        "admin": "admin",
        "driver": "driver",
    }
    return mapping.get(n, mapping.get(role_name, "keeper"))


def can(request: HttpRequest, perm: str) -> bool:
    role = _role_key(request.session.get("role_name"))
    return perm in ROLE_PERMS.get(role, set())


def require_login(view):
    """Простейший декоратор: без employee_id в сессии — на логин."""

    def wrapper(request, *args, **kwargs):
        if not request.session.get("employee_id"):
            return redirect("cabinet:login")
        return view(request, *args, **kwargs)

    return wrapper


def employee_context(request: HttpRequest) -> dict[str, Any]:
    if not request.session.get("employee_id"):
        return {"user_employee": None, "show_proto_banner": True}
    return {
        "show_proto_banner": True,
        "user_employee": {
            "id": request.session.get("employee_id"),
            "name": request.session.get("employee_name", "Сотрудник"),
            "role_title": request.session.get("role_name", ""),
            "warehouse_label": request.session.get("warehouse_label", ""),
        },
    }


class LoginPageView(View):
    """GET — форма входа; POST — LoginService + сессия."""

    template_name = "pages/login.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.session.get("employee_id"):
            return redirect("cabinet:home")
        return render(request, self.template_name, {"form": type("F", (), {"login": type("E", (), {"value": "", "errors": []})(), "password": type("E", (), {"errors": []})(), "non_field_errors": []})()})

    @inject
    def post(
        self,
        request: HttpRequest,
        login_service: LoginService = Provide[Container.login_service],
    ) -> HttpResponse:
        login = (request.POST.get("login") or "").strip()
        password = request.POST.get("password") or ""
        try:
            log_bll_call("LoginService.login", employee_id=None, login=login)
            auth_dto = login_service.login(login=login, password=password)
            emp = auth_dto.employee
            log_bll_ok(
                "LoginService.login",
                dto_preview(emp),
                employee_id=getattr(emp, "id", None),
            )
            request.session["employee_id"] = emp.id
            request.session["role_name"] = getattr(emp, "role_name", "") or ""
            request.session["employee_name"] = getattr(emp, "full_name", None) or getattr(emp, "name", login)
            request.session["warehouse_label"] = getattr(emp, "warehouse_title", "") or ""
            return redirect("cabinet:home")
        except BusinessError as exc:
            log_bll_error("LoginService.login", exc, employee_id=None)
            ctx = {
                "form": {
                    "login": type("E", (), {"value": login, "errors": []})(),
                    "password": type("E", (), {"errors": []})(),
                    "non_field_errors": [exc.message],
                }
            }
            return render(request, self.template_name, ctx, status=400)


class LogoutView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        request.session.flush()
        return redirect("cabinet:login")


class HomePageView(View):
    """Главная: счётчики и плитки по роли."""

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        role = _role_key(request.session.get("role_name"))
        layout = ROLE_HOME.get(role, ROLE_HOME["keeper"])

        # Список этапов для счётчиков (товары не нужны)
        try:
            log_bll_call("RouteQueryService.list_routes", employee_id=employee_id, only_active=False)
            stages = query_service.list_routes(employee_id, only_active=False)
            log_bll_ok("RouteQueryService.list_routes", count=len(stages))
        except BusinessError as exc:
            log_bll_error("RouteQueryService.list_routes", exc, employee_id=employee_id)
            stages = []

        def count_draft():
            return sum(1 for s in stages if getattr(s, "status", "") == "draft")

        def count_reserved():
            return sum(1 for s in stages if getattr(s, "status", "") == "reserved")

        def count_incoming():
            return sum(1 for s in stages if getattr(s, "status", "") == "shipped")

        def count_discrepancy():
            return sum(1 for s in stages if getattr(s, "status", "") == "discrepancy")

        def count_trips():
            me = request.session.get("employee_name", "")
            return sum(
                1
                for s in stages
                if getattr(s, "status", "") == "reserved"
                and me
                and me in (getattr(s, "driver_name", None) or "")
            )

        counter_meta = {
            "draft": {
                "t": "Черновики",
                "h": "Ещё не зарезервированы",
                "st": "draft",
                "n": count_draft(),
                "url": reverse("cabinet:shipment_list") + "?status=draft",
            },
            "reserved": {
                "t": "Ждут отправки",
                "h": "Товар в резерве",
                "st": "reserved",
                "n": count_reserved(),
                "url": reverse("cabinet:shipment_list") + "?status=reserved",
            },
            "incoming": {
                "t": "Едет к вам",
                "h": "Отправлено на ваш склад",
                "st": "shipped",
                "n": count_incoming(),
                "url": reverse("cabinet:receipt"),
            },
            "discrepancy": {
                "t": "Расхождения",
                "h": "Факт не совпал с документом",
                "st": "discrepancy",
                "n": count_discrepancy(),
                "url": reverse("cabinet:shipment_list") + "?status=discrepancy",
            },
            "trips": {
                "t": "Предстоящие рейсы",
                "h": "Зарезервированы, ждут отправки",
                "st": "reserved",
                "n": count_trips(),
                "url": reverse("cabinet:trips"),
            },
        }

        tile_meta = {
            "create": {
                "t": "Создать перевозку",
                "d": "Маршрут, товары, водитель, документы",
                "url": reverse("cabinet:shipment_create"),
            },
            "shipments": {
                "t": "Посмотреть перевозки",
                "d": "Исходящие и входящие этапы склада",
                "url": reverse("cabinet:shipment_list"),
            },
            "receipt": {
                "t": "Приёмка",
                "d": "Ввод факта и приёмка этапов",
                "url": reverse("cabinet:receipt"),
            },
            "stock": {
                "t": "Остатки",
                "d": "На складе, в резерве, доступно",
                "url": reverse("cabinet:stock"),
            },
            "docs": {
                "t": "Документы",
                "d": "Накладные, акты, фото",
                "url": reverse("cabinet:docs"),
            },
            "employees": {
                "t": "Сотрудники",
                "d": "Регистрация и блокировка",
                "url": reverse("cabinet:employees"),
            },
            "refs": {
                "t": "Справочники",
                "d": "Товары, склады, единицы",
                "url": reverse("cabinet:refs"),
            },
            "trips": {
                "t": "Мои рейсы",
                "d": "Этапы, где вы водитель",
                "url": reverse("cabinet:trips"),
            },
        }

        ctx = employee_context(request)
        ctx.update(
            {
                "counters": [counter_meta[k] for k in layout["counters"] if k in counter_meta],
                "main_tiles": [tile_meta[k] for k in layout["main"] if k in tile_meta],
                "extra_tiles": [tile_meta[k] for k in layout["extra"] if k in tile_meta],
            }
        )
        return render(request, "pages/home.html", ctx)


class ShipmentListPageView(View):
    """Список перевозок / «Мои рейсы»."""

    trips_only = False

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        q = (request.GET.get("q") or "").strip()
        status_filter = request.GET.get("status") or "all"

        try:
            log_bll_call("RouteQueryService.list_routes", employee_id=employee_id, only_active=False)
            stages = query_service.list_routes(employee_id, only_active=False)
            log_bll_ok("RouteQueryService.list_routes", count=len(stages))
        except BusinessError as exc:
            log_bll_error("RouteQueryService.list_routes", exc, employee_id=employee_id)
            stages = []

        rows = []
        for s in stages:
            st = getattr(s, "status", "") or ""
            if status_filter != "all" and st != status_filter:
                continue
            shipment_id = getattr(s, "shipment_id", None) or getattr(s, "id", None)
            driver = getattr(s, "driver_name", None) or getattr(s, "driver", None)
            creator = getattr(s, "creator_name", None) or getattr(s, "creator", "") or ""
            from_name = getattr(s, "from_warehouse_title", None) or getattr(s, "from_name", "—")
            to_name = getattr(s, "to_warehouse_title", None) or getattr(s, "to_name", "—")
            planned = getattr(s, "planned_date", None) or ""
            if hasattr(planned, "strftime"):
                planned = planned.strftime("%d.%m.%Y")

            if self.trips_only:
                me = request.session.get("employee_name", "")
                if not me or me not in (driver or ""):
                    continue

            if q:
                blob = " ".join(
                    str(x).lower()
                    for x in (shipment_id, st, STATUS_LABELS.get(st, st), driver, creator, from_name, to_name)
                )
                if q.lower().lstrip("№") not in blob and q.lower() not in blob:
                    continue

            rows.append(
                {
                    "shipment_id": shipment_id,
                    "stage_index": getattr(s, "stage_number", None) or getattr(s, "index", 1),
                    "stages_total": getattr(s, "stages_count", None) or 1,
                    "from_name": from_name,
                    "to_name": to_name,
                    "dir": "in" if getattr(s, "is_incoming", False) else "out",
                    "planned_date": planned,
                    "driver": driver,
                    "creator": creator,
                    "stage_status": st,
                    "stage_status_label": STATUS_LABELS.get(st, st),
                }
            )

        ctx = employee_context(request)
        ctx.update(
            {
                "page_title": "Мои рейсы" if self.trips_only else ("Все перевозки" if can(request, "view_all") else "Перевозки"),
                "page_sub": (
                    "Этапы, где вы назначены водителем"
                    if self.trips_only
                    else ("Перевозки всех складов" if can(request, "view_all") else "Исходящие и входящие этапы вашего склада")
                ),
                "can_create": can(request, "create") and not self.trips_only,
                "trips_only": self.trips_only,
                "q": q,
                "status_filter": status_filter,
                "status_filters": STATUS_FILTERS,
                "rows": rows,
            }
        )
        return render(request, "pages/shipment_list.html", ctx)


class ShipmentDetailPageView(View):
    """Карточка перевозки: этапы, документы, действия reserve/ship/cancel."""

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        shipment_id: int,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            log_bll_call(
                "RouteQueryService.get_shipment_progress",
                employee_id=employee_id,
                shipment_id=shipment_id,
            )
            shipment = query_service.get_shipment_progress(employee_id, shipment_id)
            log_bll_ok(
                "RouteQueryService.get_shipment_progress",
                dto_preview(shipment),
            )
        except BusinessError as exc:
            log_bll_error(
                "RouteQueryService.get_shipment_progress",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
            return redirect("cabinet:shipment_list")

        status = getattr(shipment, "status", "") or ""
        planned = getattr(shipment, "planned_date", "") or ""
        if hasattr(planned, "strftime"):
            planned = planned.strftime("%d.%m.%Y")

        route = getattr(shipment, "route", None) or getattr(shipment, "warehouses", None) or []
        route_nodes = []
        our_wh = request.session.get("warehouse_id")
        for w in route:
            wid = getattr(w, "id", w) if not isinstance(w, dict) else w.get("id")
            title = getattr(w, "title", None) or (w.get("title") if isinstance(w, dict) else str(w))
            city = getattr(w, "address", None) or (w.get("address") if isinstance(w, dict) else "")
            route_nodes.append({"title": title, "city": city, "mine": our_wh and wid == our_wh})

        stages_out = []
        raw_stages = getattr(shipment, "stages", None) or []
        for i, stg in enumerate(raw_stages):
            st = getattr(stg, "status", "") or ""
            items_raw = getattr(stg, "items", None) or []
            items = []
            has_comments = False
            for it in items_raw:
                qty_doc = getattr(it, "quantity", None) or getattr(it, "qty_doc", None)
                qty_fact = getattr(it, "fact_quantity", None) or getattr(it, "qty_fact", None)
                comment = getattr(it, "comment", None) or ""
                if comment:
                    has_comments = True
                items.append(
                    {
                        "product_id": getattr(it, "product_id", None),
                        "article": getattr(it, "article_number", None) or getattr(it, "article", ""),
                        "name": getattr(it, "product_name", None) or getattr(it, "name", ""),
                        "unit": getattr(it, "measurement_name", None) or getattr(it, "unit", ""),
                        "qty_doc": qty_doc,
                        "qty_fact": qty_fact,
                        "comment": comment,
                        "diff": qty_fact is not None and qty_doc is not None and qty_fact != qty_doc,
                    }
                )
            docs_raw = getattr(stg, "documents", None) or getattr(stg, "docs", None) or []
            docs = []
            for d in docs_raw:
                name = getattr(d, "file_name", None) or getattr(d, "name", "file")
                ext = (name.rsplit(".", 1)[-1] if "." in name else "").upper()[:4]
                size_b = getattr(d, "size_bytes", None)
                size_label = ""
                if size_b is not None:
                    size_label = f"{max(1, round(size_b/1024))} КБ" if size_b < 1048576 else f"{size_b/1048576:.1f} МБ".replace(".", ",")
                docs.append(
                    {
                        "id": getattr(d, "id", None),
                        "name": name,
                        "ext": ext,
                        "size": size_label or getattr(d, "size_label", None) or getattr(d, "size", ""),
                        "by": getattr(d, "uploaded_by_name", None) or getattr(d, "by", ""),
                        "at": getattr(d, "uploaded_at", None) or getattr(d, "at", ""),
                        "storage_path": getattr(d, "storage_path", "") or "",
                    }
                )

            stage_id = getattr(stg, "id", None)
            at_my = True  # детальная проверка склада — в BLL
            stages_out.append(
                {
                    "id": stage_id,
                    "index": i + 1,
                    "from_name": getattr(stg, "from_warehouse_title", "") or "",
                    "to_name": getattr(stg, "to_warehouse_title", "") or "",
                    "status": st,
                    "status_label": STATUS_LABELS.get(st, st),
                    "driver": getattr(stg, "driver_name", None),
                    "shipped_at": getattr(stg, "shipped_at", None),
                    "items": items,
                    "show_fact": st in ("received", "discrepancy"),
                    "has_comments": has_comments,
                    "docs": docs,
                    "has_docs": bool(docs),
                    "can_attach": can(request, "create") and st == "draft" and i == 0,
                    "can_reserve": can(request, "dispatch") and st == "draft" and i == 0 and at_my,
                    "can_ship": can(request, "dispatch") and st == "reserved" and at_my,
                    "can_go_receipt": can(request, "accept") and st == "shipped",
                }
            )

        cancellable = all(
            (getattr(s, "status", "") in ("draft", "waiting", "reserved")) for s in raw_stages
        ) if raw_stages else False

        ctx = employee_context(request)
        ctx.update(
            {
                "shipment": {
                    "id": shipment_id,
                    "status": status,
                    "status_label": STATUS_LABELS.get(status, status),
                    "planned_date": planned,
                    "creator": getattr(shipment, "creator_name", None) or getattr(shipment, "creator", ""),
                },
                "route_nodes": route_nodes,
                "stages": stages_out,
                "can_cancel": can(request, "cancel") and cancellable,
                "can_delete": can(request, "create") and status == "draft",
            }
        )
        return render(request, "pages/shipment_detail.html", ctx)


class ShipmentCreatePageView(View):
    """Форма новой перевозки → ShipmentDraftService.create_draft."""

    @method_decorator(require_login)
    def get(self, request: HttpRequest) -> HttpResponse:
        if not can(request, "create"):
            messages.error(request, "Недостаточно прав для создания перевозки")
            return redirect("cabinet:home")
        return self._render(request)

    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
    ) -> HttpResponse:
        if not can(request, "create"):
            messages.error(request, "Недостаточно прав")
            return redirect("cabinet:home")

        # UI-кнопки формы (добавить/убрать шаг/товар) — без сохранения
        if "add_step" in request.POST or "remove_step" in request.POST or "add_item" in request.POST or "remove_item" in request.POST:
            return self._render(request, from_post=True)

        if "create" not in request.POST:
            return self._render(request, from_post=True)

        employee_id = request.session["employee_id"]
        planned_date = request.POST.get("planned_date")
        route_wh = [int(x) for x in request.POST.getlist("route_wh") if x]
        # первый склад — склад сотрудника; в прототипе он фиксирован
        our = request.session.get("warehouse_id") or 1
        route = [our] + route_wh

        products = request.POST.getlist("item_product")
        qtys = request.POST.getlist("item_qty")
        items = []
        for pid, q in zip(products, qtys):
            try:
                items.append({"product_id": int(pid), "quantity": str(q).replace(",", ".")})
            except (ValueError, InvalidOperation):
                continue

        driver_raw = request.POST.get("driver_id") or None
        driver_id = int(driver_raw) if driver_raw else None

        documents = []
        for f in request.FILES.getlist("documents"):
            # web сохраняет файл, BLL получает только NewStageDocument
            rel_path = default_storage.save(
                f"stage_docs/draft/{f.name}",
                ContentFile(f.read()),
            )
            documents.append(
                NewStageDocument(
                    file_name=f.name,
                    storage_path=rel_path,
                    content_type=getattr(f, "content_type", None),
                    size_bytes=getattr(f, "size", None),
                )
            )

        # items: Sequence[NewStageItem]
        stage_items = []
        for it in items:
            try:
                stage_items.append(
                    NewStageItem(
                        product_id=int(it["product_id"]),
                        quantity=Decimal(str(it["quantity"])),
                    )
                )
            except (InvalidOperation, ValueError, KeyError, TypeError):
                continue

        try:
            # planned_date: date
            from datetime import date as date_cls
            if isinstance(planned_date, str) and planned_date:
                y, m, d = planned_date.split("-")
                planned_date = date_cls(int(y), int(m), int(d))

            log_bll_call(
                "ShipmentDraftService.create_draft",
                employee_id=employee_id,
                planned_date=str(planned_date),
                route=route,
                items=dto_preview(stage_items),
                driver_id=driver_id,
                documents=dto_preview(documents),
            )
            shipment_dto = draft_service.create_draft(
                employee_id=employee_id,
                planned_date=planned_date,
                route=route,
                items=stage_items,
                driver_id=driver_id,
                documents=documents,
            )
            log_bll_ok("ShipmentDraftService.create_draft", dto_preview(shipment_dto))
            sid = getattr(shipment_dto, "id", None)
            messages.success(request, f"Черновик №{sid} создан")
            if sid:
                return redirect("cabinet:shipment_detail", shipment_id=sid)
            return redirect("cabinet:shipment_list")
        except BusinessError as exc:
            log_bll_error("ShipmentDraftService.create_draft", exc, employee_id=employee_id)
            return self._render(request, from_post=True, error=exc.message)

    def _render(self, request: HttpRequest, from_post: bool = False, error: str | None = None) -> HttpResponse:
        # Минимальный контекст формы; справочники складов/товаров — из сессии/заглушек,
        # пока нет отдельного query-сервиса справочников.
        route_steps = [2]
        items = [{"product_id": 1, "qty": "1", "unit": "шт"}]
        if from_post:
            route_steps = [int(x) for x in request.POST.getlist("route_wh") if x] or route_steps
            if "add_step" in request.POST:
                route_steps.append(route_steps[-1])
            if "remove_step" in request.POST:
                idx = int(request.POST.get("remove_step", 0))
                if 0 <= idx < len(route_steps) and len(route_steps) > 1:
                    route_steps.pop(idx)
            products = request.POST.getlist("item_product")
            qtys = request.POST.getlist("item_qty")
            items = [{"product_id": int(p), "qty": q, "unit": "шт"} for p, q in zip(products, qtys)] or items
            if "add_item" in request.POST:
                items.append({"product_id": items[0]["product_id"], "qty": "1", "unit": "шт"})
            if "remove_item" in request.POST:
                idx = int(request.POST.get("remove_item", 0))
                if 0 <= idx < len(items):
                    items.pop(idx)

        ctx = employee_context(request)
        ctx.update(
            {
                "our_warehouse": {"title": request.session.get("warehouse_label") or "Склад", "address": ""},
                "warehouses": [],  # заполнить query-сервисом справочников
                "drivers": [],
                "products": [],
                "route_steps": route_steps,
                "items": items,
                "planned_date": request.POST.get("planned_date") if from_post else "",
                "min_date": "",
                "driver_id": request.POST.get("driver_id") if from_post else "",
                "summary_route": " → ".join(["ваш склад"] + [str(x) for x in route_steps]),
                "summary_stages": len(route_steps),
                "error": error,
            }
        )
        return render(request, "pages/shipment_create.html", ctx)


class ReceiptPageView(View):
    """Список входящих shipped-этапов + форма факта."""

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        if not can(request, "accept"):
            messages.error(request, "Недостаточно прав для приёмки")
            return redirect("cabinet:home")

        employee_id = request.session["employee_id"]
        try:
            log_bll_call("RouteQueryService.list_routes", employee_id=employee_id, only_active=True)
            stages = query_service.list_routes(employee_id, only_active=True)
            log_bll_ok("RouteQueryService.list_routes", count=len(stages), filter="incoming_candidates")
        except BusinessError as exc:
            log_bll_error("RouteQueryService.list_routes", exc, employee_id=employee_id)
            stages = []

        incoming = []
        for s in stages:
            if getattr(s, "status", "") != "shipped":
                continue
            # детальные items
            stage_id = getattr(s, "id", None)
            try:
                detail = query_service.get_route(employee_id, stage_id) if stage_id else s
            except BusinessError:
                detail = s
            items = []
            for it in getattr(detail, "items", None) or []:
                items.append(
                    {
                        "product_id": getattr(it, "product_id", None),
                        "article": getattr(it, "article_number", None) or "",
                        "name": getattr(it, "product_name", None) or "",
                        "unit": getattr(it, "measurement_name", None) or "",
                        "qty_doc": getattr(it, "quantity", None),
                    }
                )
            incoming.append(
                {
                    "id": stage_id,
                    "shipment_id": getattr(s, "shipment_id", None),
                    "index": getattr(s, "stage_number", 1),
                    "stages_total": getattr(s, "stages_count", 1),
                    "from_name": getattr(s, "from_warehouse_title", ""),
                    "to_name": getattr(s, "to_warehouse_title", ""),
                    "driver": getattr(s, "driver_name", None),
                    "shipped_at": getattr(s, "shipped_at", None),
                    "items": items,
                }
            )

        ctx = employee_context(request)
        ctx["incoming"] = incoming
        return render(request, "pages/receipt.html", ctx)


class StockPageView(View):
    """Остатки склада сотрудника."""

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        q = (request.GET.get("q") or "").strip().lower()
        try:
            log_bll_call(
                "RouteQueryService.get_stock_by_employee_warehouse",
                employee_id=employee_id,
            )
            stocks = query_service.get_stock_by_employee_warehouse(employee_id)
            log_bll_ok(
                "RouteQueryService.get_stock_by_employee_warehouse",
                count=len(stocks),
            )
        except (BusinessError, AttributeError) as exc:
            log_bll_error(
                "RouteQueryService.get_stock_by_employee_warehouse",
                exc if isinstance(exc, Exception) else Exception(str(exc)),
                employee_id=employee_id,
            )
            stocks = []

        rows = []
        for s in stocks:
            article = getattr(s, "article_number", "")
            name = getattr(s, "product_name", "")
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

        ctx = employee_context(request)
        ctx.update(
            {
                "warehouse_label": request.session.get("warehouse_label") or "Ваш склад",
                "q": request.GET.get("q") or "",
                "rows": rows,
            }
        )
        return render(request, "pages/stock.html", ctx)


class DocsPageView(View):
    """Реестр документов по этапам (агрегация через list_routes + list_documents)."""

    @method_decorator(require_login)
    @inject
    def get(
        self,
        request: HttpRequest,
        query_service: RouteQueryService = Provide[Container.query_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        docs = []
        try:
            log_bll_call("RouteQueryService.list_routes", employee_id=employee_id, only_active=False, purpose="docs")
            stages = query_service.list_routes(employee_id, only_active=False)
            log_bll_ok("RouteQueryService.list_routes", count=len(stages), purpose="docs")
            for s in stages:
                stage_id = getattr(s, "id", None)
                if not stage_id:
                    continue
                try:
                    for d in query_service.list_documents(employee_id, stage_id):
                        name = getattr(d, "file_name", None) or getattr(d, "name", "file")
                        ext = (name.rsplit(".", 1)[-1] if "." in name else "").upper()[:4]
                        docs.append(
                            {
                                "name": name,
                                "ext": ext,
                                "shipment_id": getattr(s, "shipment_id", None),
                                "stage_index": getattr(s, "stage_number", 1),
                                "by": getattr(d, "uploaded_by_name", "") or "",
                                "at": getattr(d, "uploaded_at", "") or "",
                                "size": getattr(d, "size_label", "") or "",
                                "url": getattr(d, "url", None),
                            }
                        )
                except BusinessError:
                    continue
        except BusinessError:
            pass

        ctx = employee_context(request)
        ctx["docs"] = docs
        return render(request, "pages/docs.html", ctx)

    @method_decorator(require_login)
    def post(self, request: HttpRequest) -> HttpResponse:
        # Загрузка файла — заглушка до сервиса документов в BLL
        messages.info(request, "Загрузка документа: подключите draft/dispatch attach в BLL")
        return redirect("cabinet:docs")


class EmployeesPageView(View):
    """Список сотрудников (manage). Пока заглушка без отдельного BLL-сервиса."""

    @method_decorator(require_login)
    def get(self, request: HttpRequest) -> HttpResponse:
        if not can(request, "manage"):
            messages.error(request, "Недостаточно прав")
            return redirect("cabinet:home")
        ctx = employee_context(request)
        ctx["employees"] = []  # подключить EmployeeQueryService при появлении
        return render(request, "pages/employees.html", ctx)


class EmployeeRegisterPageView(View):
    @method_decorator(require_login)
    def get(self, request: HttpRequest) -> HttpResponse:
        if not can(request, "manage"):
            return redirect("cabinet:home")
        return render(
            request,
            "pages/stub.html",
            {
                **employee_context(request),
                "page_title": "Регистрация сотрудника",
                "page_text": "Форма регистрации — в разработке (нужен BLL RegisterEmployee).",
            },
        )


class EmployeeToggleView(View):
    @method_decorator(require_login)
    def post(self, request: HttpRequest, employee_id: int) -> HttpResponse:
        if not can(request, "manage"):
            messages.error(request, "Недостаточно прав")
        else:
            messages.info(request, f"Блокировка/разблокировка сотрудника #{employee_id}: сервис в разработке")
        return redirect("cabinet:employees")


class RefsPageView(View):
    @method_decorator(require_login)
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "pages/stub.html",
            {
                **employee_context(request),
                "page_title": "Справочники",
                "page_text": "Раздел в разработке: товары, склады, единицы измерения, статусы.",
            },
        )


class StageReserveView(View):
    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        stage_id: int,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            log_bll_call(
                "ShipmentDispatchService.reserve_stage",
                employee_id=employee_id,
                stage_id=stage_id,
            )
            stage_dto = dispatch_service.reserve_stage(employee_id=employee_id, stage_id=stage_id)
            log_bll_ok("ShipmentDispatchService.reserve_stage", dto_preview(stage_dto))
            messages.success(request, "Этап зарезервирован")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDispatchService.reserve_stage",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
        # вернуться на карточку — shipment_id из referer/query
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("cabinet:shipment_list")
        return redirect(next_url)


class StageShipView(View):
    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        stage_id: int,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            log_bll_call(
                "ShipmentDispatchService.ship_stage",
                employee_id=employee_id,
                stage_id=stage_id,
            )
            stage_dto = dispatch_service.ship_stage(employee_id=employee_id, stage_id=stage_id)
            log_bll_ok("ShipmentDispatchService.ship_stage", dto_preview(stage_dto))
            messages.success(request, "Этап отправлен")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDispatchService.ship_stage",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("cabinet:shipment_list")
        return redirect(next_url)


class StageAcceptView(View):
    """
    Приёмка по контракту BLL:
      1) enter_actual_quantity(employee_id, item_id, quantity, comment?)
      2) accept_stage(employee_id, stage_id)
    В форме: fact_<item_id>, com_<item_id> (id позиции этапа, не product_id).
    """

    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        stage_id: int,
        receive_service: ShipmentReceiptService = Provide[Container.receive_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            for key, val in request.POST.items():
                if not key.startswith("fact_"):
                    continue
                item_id = int(key[5:])
                raw = (val or "").replace(",", ".").replace(" ", "")
                qty = Decimal(raw)
                comment = (request.POST.get(f"com_{item_id}") or "").strip() or None
                log_bll_call(
                    "ShipmentReceiptService.enter_actual_quantity",
                    employee_id=employee_id,
                    item_id=item_id,
                    quantity=str(qty),
                    comment=comment,
                )
                receive_service.enter_actual_quantity(
                    employee_id=employee_id,
                    item_id=item_id,
                    quantity=qty,
                    comment=comment,
                )
                log_bll_ok("ShipmentReceiptService.enter_actual_quantity", item_id=item_id)
            log_bll_call(
                "ShipmentReceiptService.accept_stage",
                employee_id=employee_id,
                stage_id=stage_id,
            )
            stage_dto = receive_service.accept_stage(employee_id=employee_id, stage_id=stage_id)
            log_bll_ok("ShipmentReceiptService.accept_stage", dto_preview(stage_dto))
            messages.success(request, "Этап принят")
        except (BusinessError, InvalidOperation, ValueError) as exc:
            log_bll_error(
                "ShipmentReceiptService.accept_stage",
                exc if isinstance(exc, Exception) else Exception(str(exc)),
                employee_id=employee_id,
            )
            msg = getattr(exc, "message", None) or str(exc)
            messages.error(request, msg)
        return redirect("cabinet:receipt")


class StageAttachDocView(View):
    """
    Прикрепление документа к этапу-черновику.

    Контракт BLL (ShipmentDraftService.attach_document):
      - web-слой СНАЧАЛА сохраняет файл на диск (MEDIA);
      - в BLL уходит NewStageDocument(file_name, storage_path, content_type, size_bytes);
      - BLL пишет только метаданные в StageDocuments, файл не трогает.
      - remove_document — только запись в БД; файл на диске удаляет web.
    """

    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        stage_id: int,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        files = request.FILES.getlist("document") or request.FILES.getlist("documents")
        if not files:
            messages.error(request, "Файл не выбран")
            return self._back(request, stage_id)

        attached = 0
        for f in files:
            try:
                # 1) сохраняем файл на диск (относительный путь в MEDIA)
                rel_path = default_storage.save(
                    f"stage_docs/{stage_id}/{f.name}",
                    ContentFile(f.read()),
                )
                doc = NewStageDocument(
                    file_name=f.name,
                    storage_path=rel_path,
                    content_type=getattr(f, "content_type", None),
                    size_bytes=getattr(f, "size", None),
                )
                log_bll_call(
                    "ShipmentDraftService.attach_document",
                    employee_id=employee_id,
                    stage_id=stage_id,
                    document=dto_preview(doc),
                )
                doc_dto = draft_service.attach_document(
                    employee_id=employee_id,
                    stage_id=stage_id,
                    document=doc,
                )
                log_bll_ok("ShipmentDraftService.attach_document", dto_preview(doc_dto))
                attached += 1
            except BusinessError as exc:
                log_bll_error(
                    "ShipmentDraftService.attach_document",
                    exc,
                    employee_id=employee_id,
                )
                messages.error(request, getattr(exc, "message", str(exc)))
            except Exception as exc:  # noqa: BLE001 — показать пользователю
                log_bll_error(
                    "ShipmentDraftService.attach_document",
                    exc,
                    employee_id=employee_id,
                )
                messages.error(request, f"Не удалось сохранить «{getattr(f, 'name', 'file')}»: {exc}")

        if attached:
            messages.success(
                request,
                f"Прикреплено документов: {attached}" if attached > 1 else f"Документ «{files[0].name}» прикреплён",
            )
        return self._back(request, stage_id)

    def _back(self, request: HttpRequest, stage_id: int) -> HttpResponse:
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        if next_url:
            return redirect(next_url)
        return redirect("cabinet:shipment_list")


class StageRemoveDocView(View):
    """Открепление: BLL удаляет запись; файл с диска снимает web."""

    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        document_id: int,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        storage_path = (request.POST.get("storage_path") or "").strip()
        try:
            log_bll_call(
                "ShipmentDraftService.remove_document",
                employee_id=employee_id,
                document_id=document_id,
                storage_path=storage_path,
            )
            draft_service.remove_document(employee_id=employee_id, document_id=document_id)
            if storage_path and default_storage.exists(storage_path):
                default_storage.delete(storage_path)
            log_bll_ok("ShipmentDraftService.remove_document", document_id=document_id)
            messages.success(request, "Документ откреплён")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDraftService.remove_document",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("cabinet:shipment_list")
        return redirect(next_url)



class ShipmentCancelView(View):
    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        shipment_id: int,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            log_bll_call(
                "ShipmentDispatchService.cancel_shipment",
                employee_id=employee_id,
                shipment_id=shipment_id,
            )
            shipment_dto = dispatch_service.cancel_shipment(
                employee_id=employee_id, shipment_id=shipment_id
            )
            log_bll_ok("ShipmentDispatchService.cancel_shipment", dto_preview(shipment_dto))
            messages.success(request, f"Перевозка №{shipment_id} отменена")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDispatchService.cancel_shipment",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
        return redirect("cabinet:shipment_detail", shipment_id=shipment_id)


class ShipmentDeleteView(View):
    @method_decorator(require_login)
    @inject
    def post(
        self,
        request: HttpRequest,
        shipment_id: int,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
    ) -> HttpResponse:
        employee_id = request.session["employee_id"]
        try:
            log_bll_call(
                "ShipmentDraftService.delete_draft",
                employee_id=employee_id,
                shipment_id=shipment_id,
            )
            draft_service.delete_draft(employee_id=employee_id, shipment_id=shipment_id)
            log_bll_ok("ShipmentDraftService.delete_draft", shipment_id=shipment_id)
            messages.success(request, f"Черновик №{shipment_id} удалён")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDraftService.delete_draft",
                exc,
                employee_id=employee_id,
            )
            messages.error(request, getattr(exc, "message", str(exc)))
        except AttributeError as exc:
            log_bll_error("ShipmentDraftService.delete_draft", exc, employee_id=employee_id)
            messages.info(request, "delete_draft пока нет в BLL")
        return redirect("cabinet:shipment_list")


@method_decorator(csrf_exempt, name="dispatch")
class CreateDraftAPIView(View):
    @inject
    def post(self, request, draft_service: ShipmentDraftService = Provide[Container.draft_service], **kwargs):
        try:
            body = __import__("json").loads(request.body)
        except Exception:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        employee_id = request.session.get("employee_id", 1)
        log_bll_call(
            "ShipmentDraftService.create_draft",
            employee_id=employee_id,
            planned_date=body.get("planned_date"),
            route=body.get("route", []),
            items=dto_preview(body.get("items", [])),
            driver_id=body.get("driver_id"),
            documents=dto_preview(body.get("documents", [])),
            via="api",
        )
        try:
            dto = draft_service.create_draft(
                employee_id=employee_id,
                planned_date=body.get("planned_date"),
                route=body.get("route", []),
                items=body.get("items", []),
                driver_id=body.get("driver_id"),
                documents=body.get("documents", []),
            )
            log_bll_ok("ShipmentDraftService.create_draft", dto_preview(dto), via="api")
        except BusinessError as exc:
            log_bll_error("ShipmentDraftService.create_draft", exc, employee_id=employee_id)
            raise
        return JsonResponse(asdict(dto), status=201)


@method_decorator(csrf_exempt, name="dispatch")
class ShipStageAPIView(View):
    @inject
    def post(self, request, stage_id: int, dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service], **kwargs):
        employee_id = request.session.get("employee_id", 1)
        log_bll_call(
            "ShipmentDispatchService.ship_stage",
            employee_id=employee_id,
            stage_id=stage_id,
            via="api",
        )
        try:
            dto = dispatch_service.ship_stage(employee_id=employee_id, stage_id=stage_id)
            log_bll_ok("ShipmentDispatchService.ship_stage", dto_preview(dto), via="api")
        except BusinessError as exc:
            log_bll_error("ShipmentDispatchService.ship_stage", exc, employee_id=employee_id)
            raise
        return JsonResponse(asdict(dto), status=200)


@method_decorator(csrf_exempt, name="dispatch")
class AcceptStageAPIView(View):
    @inject
    def post(self, request, stage_id: int, receive_service: ShipmentReceiptService = Provide[Container.receive_service], **kwargs):
        employee_id = request.session.get("employee_id", 1)
        log_bll_call(
            "ShipmentReceiptService.accept_stage",
            employee_id=employee_id,
            stage_id=stage_id,
            via="api",
        )
        try:
            dto = receive_service.accept_stage(employee_id=employee_id, stage_id=stage_id)
            log_bll_ok("ShipmentReceiptService.accept_stage", dto_preview(dto), via="api")
        except BusinessError as exc:
            log_bll_error("ShipmentReceiptService.accept_stage", exc, employee_id=employee_id)
            raise
        return JsonResponse(asdict(dto), status=200)


@method_decorator(csrf_exempt, name="dispatch")
class LoginAPIView(View):
    @inject
    def post(self, request, login_service: LoginService = Provide[Container.login_service], **kwargs):
        try:
            body = __import__("json").loads(request.body)
        except Exception:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)
        log_bll_call("LoginService.login", employee_id=None, login=body.get("login"), via="api")
        try:
            auth_dto = login_service.login(login=body.get("login"), password=body.get("password"))
            log_bll_ok("LoginService.login", dto_preview(auth_dto.employee), via="api")
        except BusinessError as exc:
            log_bll_error("LoginService.login", exc, employee_id=None)
            raise
        request.session["employee_id"] = auth_dto.employee.id
        request.session["role_name"] = getattr(auth_dto.employee, "role_name", "")
        return JsonResponse(asdict(auth_dto.employee), status=200)


class StockListAPIView(View):
    @inject
    def get(self, request, query_service: RouteQueryService = Provide[Container.query_service], **kwargs):
        employee_id = request.session.get("employee_id", 1)
        log_bll_call(
            "RouteQueryService.get_stock_by_employee_warehouse",
            employee_id=employee_id,
            via="api",
        )
        try:
            stocks = query_service.get_stock_by_employee_warehouse(employee_id)
            log_bll_ok(
                "RouteQueryService.get_stock_by_employee_warehouse",
                count=len(stocks),
                via="api",
            )
        except BusinessError as exc:
            log_bll_error(
                "RouteQueryService.get_stock_by_employee_warehouse",
                exc,
                employee_id=employee_id,
            )
            raise
        return JsonResponse({"stocks": [asdict(s) for s in stocks]}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class CancelShipmentAPIView(View):
    @inject
    def post(self, request, shipment_id: int, dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service], **kwargs):
        employee_id = request.session.get("employee_id", 1)
        log_bll_call(
            "ShipmentDispatchService.cancel_shipment",
            employee_id=employee_id,
            shipment_id=shipment_id,
            via="api",
        )
        try:
            dto = dispatch_service.cancel_shipment(employee_id=employee_id, shipment_id=shipment_id)
            log_bll_ok("ShipmentDispatchService.cancel_shipment", dto_preview(dto), via="api")
        except BusinessError as exc:
            log_bll_error(
                "ShipmentDispatchService.cancel_shipment",
                exc,
                employee_id=employee_id,
            )
            raise
        return JsonResponse(asdict(dto), status=200)


# wiring
container = Container()
container.wire(modules=[__name__])
container.wire(modules=["web.views"])
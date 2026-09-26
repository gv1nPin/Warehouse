"""JSON API поверх сервисов BLL. Сотрудник берётся из токена в сессии."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from dependency_injector.wiring import Provide, inject
from container import Container

from warehouse.bll.services.auth_service import LoginService
from warehouse.bll.services.shipment_service import (
    ShipmentDispatchService,
    ShipmentDraftService,
    ShipmentReceiptService,
)
from warehouse.common.dto import NewStageItem
from warehouse.common.exceptions import ValidationError

from ..auth import api_employee_required, sign_in
from ..services import container, employee_service

from web.controller_logging import (
    log_bll_call,
    log_bll_ok,
    log_bll_error,
    dto_preview,
)

import logging
_log = logging.getLogger("web.controllers")

def _json_body(request) -> dict:
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        raise ValidationError("Невалидный JSON") from None
    if not isinstance(body, dict):
        raise ValidationError("Ожидается JSON-объект")
    return body


def _json(data, status: int = 200) -> JsonResponse:
    return JsonResponse(asdict(data), encoder=DjangoJSONEncoder, status=status)


@method_decorator(api_employee_required, name="dispatch")
class CreateDraftView(View):
    @inject
    def post(
        self,
        request,
        *args,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
        **kwargs,
    ) -> JsonResponse:
        body = _json_body(request)
        try:
            planned_date = date.fromisoformat(body.get("planned_date", ""))
            items = [
                NewStageItem(product_id=int(i["product_id"]), quantity=i["quantity"])
                for i in body.get("items", [])
            ]
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Неверная дата или список товаров") from None

        operation = "CreateDraft"
        emp_id = request.actor.employee_id
        
        # Логируем вход: исключаем пароли автоматически внутри log_bll_call
        log_bll_call(
            operation, 
            employee_id=emp_id, 
            planned_date=planned_date, 
            route=body.get("route"), 
            items=items, 
            driver_id=body.get("driver_id")
        )
        
        try:
            shipment = draft_service.create_draft(
                employee_id=emp_id,
                planned_date=planned_date,
                route=body.get("route", []),
                items=items,
                driver_id=body.get("driver_id"),
            )
            # Логируем успех (передаем сущность или её id в extra)
            log_bll_ok(operation, result=shipment)
            return _json(shipment, status=201)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=emp_id)
            raise


@method_decorator(api_employee_required, name="dispatch")
class ShipStageView(View):
    @inject
    def post(
        self,
        request,
        stage_id: int,
        *args,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs,
    ) -> JsonResponse:
        operation = "ShipStage"
        emp_id = request.actor.employee_id
        
        log_bll_call(operation, employee_id=emp_id, stage_id=stage_id)
        try:
            result = dispatch_service.ship_stage(employee_id=emp_id, stage_id=stage_id)
            log_bll_ok(operation, result=result)
            return _json(result)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=emp_id)
            raise


@method_decorator(api_employee_required, name="dispatch")
class AcceptStageView(View):
    @inject
    def post(
        self,
        request,
        stage_id: int,
        *args,
        receive_service: ShipmentReceiptService = Provide[Container.receive_service],
        **kwargs,
    ) -> JsonResponse:
        operation = "AcceptStage"
        emp_id = request.actor.employee_id
        
        log_bll_call(operation, employee_id=emp_id, stage_id=stage_id)
        try:
            result = receive_service.accept_stage(employee_id=emp_id, stage_id=stage_id)
            log_bll_ok(operation, result=result)
            return _json(result)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=emp_id)
            raise


@method_decorator(api_employee_required, name="dispatch")
class CancelShipmentView(View):
    @inject
    def post(
        self,
        request,
        shipment_id: int,
        *args,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs,
    ) -> JsonResponse:
        operation = "CancelShipment"
        emp_id = request.actor.employee_id
        
        log_bll_call(operation, employee_id=emp_id, shipment_id=shipment_id)
        try:
            result = dispatch_service.cancel_shipment(employee_id=emp_id, shipment_id=shipment_id)
            log_bll_ok(operation, result=result)
            return _json(result)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=emp_id)
            raise


@method_decorator(api_employee_required, name="dispatch")
class StockListView(View):
    @inject
    def get(
        self,
        request,
        *args,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
        **kwargs,
    ) -> JsonResponse:
        operation = "StockList"
        emp_id = request.actor.employee_id
        
        log_bll_call(operation, employee_id=emp_id)
        try:
            stocks = draft_service.list_available_stock(emp_id)
            # Передаем итог (например, количество позиций на складе)
            log_bll_ok(operation, extra={"count": len(stocks)})
            return JsonResponse({"stocks": [asdict(s) for s in stocks]}, encoder=DjangoJSONEncoder)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=emp_id)
            raise


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(View):
    """Вход: без import EmployeeService на уровне модуля (см. services.employee_service)."""

    @inject
    def post(
        self,
        request,
        *args,
        login_service: LoginService = Provide[Container.login_service],
        **kwargs,
    ) -> JsonResponse:
        body = _json_body(request)
        operation = "Login"
        
        # Логируем вход: передаем payload. password автоматически вырежется благодаря _REDACT_KEYS
        log_bll_call(operation, employee_id=None, login=body.get("login"), password=body.get("password"))
        try:
            token = login_service.login(login=body.get("login"), password=body.get("password"))
            warehouse = employee_service().get_warehouse(token.employee.id)
            sign_in(request, token, warehouse)
            
            log_bll_ok(operation, result=token.employee)
            return _json(token.employee)
        except Exception as exc:
            log_bll_error(operation, exc, employee_id=None)
            raise


container.wire(modules=[__name__])

"""JSON API поверх сервисов BLL. Сотрудник берётся из токена в сессии."""

<<<<<<< HEAD
from __future__ import annotations

=======
>>>>>>> main
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
<<<<<<< HEAD
=======
from warehouse.bll.services.employee_service import EmployeeService
>>>>>>> main
from warehouse.bll.services.shipment_service import (
    ShipmentDispatchService,
    ShipmentDraftService,
    ShipmentReceiptService,
)
from warehouse.common.dto import NewStageItem
from warehouse.common.exceptions import ValidationError

from ..auth import api_employee_required, sign_in
<<<<<<< HEAD
from ..services import container, employee_service
=======
from ..services import container
>>>>>>> main


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


<<<<<<< HEAD
@method_decorator(api_employee_required, name="dispatch")
class CreateDraftView(View):
=======
@method_decorator(api_employee_required, name='dispatch')
class CreateDraftView(View):
    """Создание черновика перевозки."""

>>>>>>> main
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
<<<<<<< HEAD
            items = [
                NewStageItem(product_id=int(i["product_id"]), quantity=i["quantity"])
                for i in body.get("items", [])
            ]
=======
            items = [NewStageItem(product_id=int(i["product_id"]), quantity=i["quantity"]) for i in body.get("items", [])]
>>>>>>> main
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Неверная дата или список товаров") from None

        shipment = draft_service.create_draft(
            employee_id=request.actor.employee_id,
            planned_date=planned_date,
            route=body.get("route", []),
            items=items,
            driver_id=body.get("driver_id"),
        )
        return _json(shipment, status=201)


<<<<<<< HEAD
@method_decorator(api_employee_required, name="dispatch")
class ShipStageView(View):
=======
@method_decorator(api_employee_required, name='dispatch')
class ShipStageView(View):
    """Отправка этапа со склада."""

>>>>>>> main
    @inject
    def post(
        self,
        request,
        stage_id: int,
        *args,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs,
    ) -> JsonResponse:
<<<<<<< HEAD
        return _json(
            dispatch_service.ship_stage(employee_id=request.actor.employee_id, stage_id=stage_id)
        )


@method_decorator(api_employee_required, name="dispatch")
class AcceptStageView(View):
=======
        return _json(dispatch_service.ship_stage(employee_id=request.actor.employee_id, stage_id=stage_id))


@method_decorator(api_employee_required, name='dispatch')
class AcceptStageView(View):
    """Приёмка этапа на складе назначения."""

>>>>>>> main
    @inject
    def post(
        self,
        request,
        stage_id: int,
        *args,
        receive_service: ShipmentReceiptService = Provide[Container.receive_service],
        **kwargs,
    ) -> JsonResponse:
<<<<<<< HEAD
        return _json(
            receive_service.accept_stage(employee_id=request.actor.employee_id, stage_id=stage_id)
        )


@method_decorator(api_employee_required, name="dispatch")
class CancelShipmentView(View):
=======
        return _json(receive_service.accept_stage(employee_id=request.actor.employee_id, stage_id=stage_id))


@method_decorator(api_employee_required, name='dispatch')
class CancelShipmentView(View):
    """Отмена перевозки до отправки."""

>>>>>>> main
    @inject
    def post(
        self,
        request,
        shipment_id: int,
        *args,
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs,
    ) -> JsonResponse:
<<<<<<< HEAD
        return _json(
            dispatch_service.cancel_shipment(
                employee_id=request.actor.employee_id, shipment_id=shipment_id
            )
        )


@method_decorator(api_employee_required, name="dispatch")
class StockListView(View):
=======
        return _json(dispatch_service.cancel_shipment(employee_id=request.actor.employee_id, shipment_id=shipment_id))


@method_decorator(api_employee_required, name='dispatch')
class StockListView(View):
    """Свободные остатки склада сотрудника."""

>>>>>>> main
    @inject
    def get(
        self,
        request,
        *args,
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
        **kwargs,
    ) -> JsonResponse:
        stocks = draft_service.list_available_stock(request.actor.employee_id)
        return JsonResponse({"stocks": [asdict(s) for s in stocks]}, encoder=DjangoJSONEncoder)


<<<<<<< HEAD
@method_decorator(csrf_exempt, name="dispatch")
class LoginView(View):
    """Вход: без import EmployeeService на уровне модуля (см. services.employee_service)."""
=======
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    """Вход по логину и паролю: токен кладётся в сессию, как на странице входа."""
>>>>>>> main

    @inject
    def post(
        self,
        request,
        *args,
        login_service: LoginService = Provide[Container.login_service],
<<<<<<< HEAD
=======
        employee_service: EmployeeService = Provide[Container.employee_service],
>>>>>>> main
        **kwargs,
    ) -> JsonResponse:
        body = _json_body(request)
        token = login_service.login(login=body.get("login"), password=body.get("password"))
<<<<<<< HEAD
        warehouse = employee_service().get_warehouse(token.employee.id)
        sign_in(request, token, warehouse)
=======
        sign_in(request, token, employee_service.get_warehouse(token.employee.id))
>>>>>>> main
        return _json(token.employee)


container.wire(modules=[__name__])

import json
from dataclasses import asdict
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

# Инструменты автоматической инжекции зависимостей
from dependency_injector.wiring import Provide, inject
from container import Container

# Импортируем классы сервисов БЛ строго для типизации в аргументах
from warehouse.bll.services.shipment_service import (
    ShipmentDraftService, 
    ShipmentDispatchService,
    ShipmentReceiptService,
    RouteQueryService
)
from warehouse.bll.services.auth_service import LoginService


@method_decorator(csrf_exempt, name='dispatch')
class CreateDraftView(View):
    """1. РАЗДЕЛ: Новая перевозка (Создание черновика)."""
    
    @inject
    def post(
        self, 
        request, 
        *args, 
        draft_service: ShipmentDraftService = Provide[Container.draft_service], # Авто-инжекция
        **kwargs
    ) -> JsonResponse:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        employee_id = request.session.get('employee_id', 1)

        shipment_dto = draft_service.create_draft(
            employee_id=employee_id,
            planned_date=body.get("planned_date"),
            route=body.get("route", []),
            items=body.get("items", []),
            driver_id=body.get("driver_id"),
            documents=body.get("documents", [])
        )
        return JsonResponse(asdict(shipment_dto), encoder=DjangoJSONEncoder, status=201)


@method_decorator(csrf_exempt, name='dispatch')
class ShipStageView(View):
    """2. РАЗДЕЛ: Отгрузка этапа перевозки со склада (Dispatch)."""
    
    @inject
    def post(
        self, 
        request, 
        stage_id: int, # Переменная из URL роутера Django
        *args, 
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs
    ) -> JsonResponse:
        employee_id = request.session.get('employee_id', 1)
        
        # Вызываем доменный сервис отгрузки (внутри сработает резерв остатков)
        stage_dto = dispatch_service.ship_stage(employee_id=employee_id, stage_id=stage_id)
        return JsonResponse(asdict(stage_dto), encoder=DjangoJSONEncoder, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class AcceptStageView(View):
    """3. РАЗДЕЛ: Приёмка этапа фуры на транзитном/финальном складе (Receive + Coordinator)."""
    
    @inject
    def post(
        self, 
        request, 
        stage_id: int, 
        *args, 
        receive_service: ShipmentReceiptService = Provide[Container.receive_service],
        **kwargs
    ) -> JsonResponse:
        employee_id = request.session.get('employee_id', 1)
        
        # Сервис приёмки зафиксирует фактические объёмы и автоматически 
        # вызовет ShipmentTransitCoordinator для движения груза на следующий этап
        stage_dto = receive_service.accept_stage(employee_id=employee_id, stage_id=stage_id)
        return JsonResponse(asdict(stage_dto), encoder=DjangoJSONEncoder, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(View):
    """4. РАЗДЕЛ: Вход (Авторизация сотрудников)."""
    
    @inject
    def post(
        self, 
        request, 
        *args, 
        login_service: LoginService = Provide[Container.login_service],
        **kwargs
    ) -> JsonResponse:
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        auth_dto = login_service.login(
            login=body.get("login"),
            password=body.get("password")
        )
        
        request.session['employee_id'] = auth_dto.employee.id
        request.session['role_name'] = auth_dto.employee.role_name
        
        return JsonResponse(asdict(auth_dto.employee), status=200)


class StockListView(View):
    """5. РАЗДЕЛ: Остатки на складах (Чтение через Query-сервис)."""
    
    @inject
    def get(
        self, 
        request, 
        *args, 
        query_service: RouteQueryService = Provide[Container.query_service],
        **kwargs
    ) -> JsonResponse:
        employee_id = request.session.get('employee_id', 1)
        
        # Получаем данные остатков без ручного открытия контекстов uow во views
        stocks = query_service.get_stock_by_employee_warehouse(employee_id)
        return JsonResponse({"stocks": [asdict(s) for s in stocks]}, encoder=DjangoJSONEncoder, status=200)

@method_decorator(csrf_exempt, name='dispatch')
class CancelShipmentView(View):
    """РАЗДЕЛ: Отмена перевозки до момента её отправки."""
    
    @inject
    def post(
        self, 
        request, 
        shipment_id: int, # ID забираем прямо из URL-маршрута
        *args, 
        dispatch_service: ShipmentDispatchService = Provide[Container.dispatch_service],
        **kwargs
    ) -> JsonResponse:
        employee_id = request.session.get('employee_id', 1)
        
        # Вызываем доменный метод отмены, он вернет обновленный ShipmentDTO
        shipment_dto = dispatch_service.cancel_shipment(
            employee_id=employee_id, 
            shipment_id=shipment_id
        )
        return JsonResponse(asdict(shipment_dto), encoder=DjangoJSONEncoder, status=200)

class PrototypeCabinetView(TemplateView):
    """6. РЕНДЕРИНГ: Отдача фронтенд-прототипа."""
    template_name = "index.html"


# Сборка графа и проклейка зависимостей строго в самом низу файла!
container = Container()
container.wire(modules=[__name__])

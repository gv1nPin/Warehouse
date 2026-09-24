import json
from dataclasses import asdict
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

# Подключаем инструменты инжекции от dependency_injector
from dependency_injector.wiring import Provide, inject
from container import Container
from warehouse.bll.services.shipment_service import ShipmentDraftService


@method_decorator(csrf_exempt, name='dispatch')
class CreateDraftView(View):
    """Контроллер Django с автоматическим внедрением зависимостей (DI)."""

    @inject
    def post(
        self, 
        request, 
        *args, 
        # Контейнер автоматически подставит инстанс сервиса в этот аргумент
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
        **kwargs
    ) -> JsonResponse:
        
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        employee_id = request.session.get('employee_id', 1)

        # Вызываем внедренный сервис бизнес-логики
        shipment_dto = draft_service.create_draft(
            employee_id=employee_id,
            planned_date=body.get("planned_date"),
            route=body.get("route", []),
            items=body.get("items", []),
            driver_id=body.get("driver_id"),
            documents=body.get("documents", [])
        )

        data = asdict(shipment_dto)
        return JsonResponse(data, encoder=DjangoJSONEncoder, status=201)

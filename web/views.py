import json
from dataclasses import asdict
from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

# Инструменты DI
from dependency_injector.wiring import Provide, inject
from container import Container
from warehouse.bll.services.shipment_service import ShipmentDraftService

# ЖЕЛЕЗНЫЙ ФИКС ИНТЕГРАЦИИ:
# Создаем инстанс контейнера и проклеиваем текущий модуль views прямо здесь.
# Это гарантирует атомарную загрузку всех классов для Django без ImportError!
container = Container()
container.wire(modules=[__name__])


@method_decorator(csrf_exempt, name='dispatch')
class CreateDraftView(View):
    """Контроллер Django для создания черновиков перевозок."""

    @inject
    def post(
        self, 
        request, 
        *args, 
        draft_service: ShipmentDraftService = Provide[Container.draft_service],
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

        data = asdict(shipment_dto)
        return JsonResponse(data, encoder=DjangoJSONEncoder, status=201)


class PrototypeCabinetView(TemplateView):
    """Контроллер для отображения фронтенд-прототипа личного кабинета."""
    template_name = "index.html"

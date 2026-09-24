import json
from dataclasses import asdict
from django.http import JsonResponse
from django.views import View

from warehouse.bll.services.shipment_service import ShipmentDraftService
from warehouse.dal.unit_of_work import UnitOfWork
from warehouse.bll.services.auth_service import AccessService

class CreateDraftView(View):
    """Контроллер Django, использующий напрямую ваши доменные DTO."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Фабрика UnitOfWork для изоляции сессий в потоках Django
        self.uow_factory = lambda: UnitOfWork()
        self.access_service = AccessService() 
        self.service = ShipmentDraftService(self.uow_factory, self.access_service)

    def post(self, request):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Невалидный JSON"}, status=400)

        employee_id = request.session.get('employee_id', 1)

        # 1. Сервис выполняет логику внутри транзакции SQLAlchemy 2.0
        # 2. Напрямую возвращает строгий доменный ShipmentDTO
        shipment_dto = self.service.create_draft(
            employee_id=employee_id,
            planned_date=body.get("planned_date"),
            route=body.get("route", []),
            items=body.get("items", []),
            driver_id=body.get("driver_id"),
            documents=body.get("documents", [])
        )

        # Функция asdict() автоматически превратит ShipmentDTO и все вложенные 
        # StageDTO, Decimal, даты в валидный словарь для Django JsonResponse.
        return JsonResponse(asdict(shipment_dto), status=201)

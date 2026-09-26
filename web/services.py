"""Готовые сервисы BLL для view. Во view сервис берём только отсюда."""

from django.conf import settings

from container import Container
from warehouse.bll.services.auth_service import LoginService
from warehouse.bll.services.employee_service import EmployeeService
from warehouse.bll.services.operation_history_service import OperationHistoryService
from warehouse.bll.services.shipment_service import (
    RouteQueryService,
    ShipmentDispatchService,
    ShipmentDraftService,
    ShipmentReceiptService,
)
from warehouse.bll.services.stock_service import StockQueryService

container = Container()
container.config.from_dict(
    {"jwt_secret": settings.JWT_SECRET, "jwt_expire_minutes": settings.JWT_EXPIRE_MINUTES}
)


def login_service() -> LoginService:
    return container.login_service()


def employee_service() -> EmployeeService:
    return container.employee_service()


def draft_service() -> ShipmentDraftService:
    return container.draft_service()


def dispatch_service() -> ShipmentDispatchService:
    return container.dispatch_service()


def receipt_service() -> ShipmentReceiptService:
    return container.receive_service()


def route_service() -> RouteQueryService:
    return container.query_service()


def stock_service() -> StockQueryService:
    return container.stock_query()


def history_service() -> OperationHistoryService:
    return container.history_service()

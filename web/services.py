"""Готовые сервисы BLL для view. Во view сервис берём только отсюда."""

<<<<<<< HEAD
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from container import Container

if TYPE_CHECKING:
    from warehouse.bll.services.auth_service import LoginService
    from warehouse.bll.services.employee_service.employee_service import EmployeeService
    from warehouse.bll.services.shipment_service import (
        RouteQueryService,
        ShipmentDispatchService,
        ShipmentDraftService,
        ShipmentReceiptService,
    )
=======
from django.conf import settings

from container import Container
from warehouse.bll.services.auth_service import LoginService
from warehouse.bll.services.employee_service import EmployeeService
from warehouse.bll.services.shipment_service import (
    RouteQueryService,
    ShipmentDispatchService,
    ShipmentDraftService,
    ShipmentReceiptService,
)
>>>>>>> main

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

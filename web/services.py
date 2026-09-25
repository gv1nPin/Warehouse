"""Готовые сервисы BLL для view. Во view сервис берём только отсюда."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

from container import Container

if TYPE_CHECKING:
    from warehouse.bll.services.auth_service import LoginService
    from warehouse.bll.services.employee_service import EmployeeService
    from warehouse.bll.services.operation_history_service import OperationHistoryService
    from warehouse.bll.services.shipment_service import (
        RouteQueryService,
        ShipmentDispatchService,
        ShipmentDraftService,
        ShipmentReceiptService,
    )

container = Container()

_config = getattr(container, "config", None)
if _config is not None and hasattr(_config, "from_dict"):
    try:
        _config.from_dict(
            {
                "jwt_secret": getattr(settings, "JWT_SECRET", None),
                "jwt_expire_minutes": int(getattr(settings, "JWT_EXPIRE_MINUTES", 8 * 60)),
            }
        )
    except Exception:
        pass


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


def history_service() -> OperationHistoryService:
    return container.history_service()

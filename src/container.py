from dependency_injector import containers, providers

from warehouse.dal.database import scoped_session_factory
from warehouse.dal.unit_of_work import UnitOfWork

from warehouse.bll.services.shipment_service import (
    ShipmentDraftService,
    ShipmentDispatchService,
    ShipmentReceiptService,
    RouteQueryService,
    ShipmentTransitCoordinator
)
from warehouse.bll.services.auth_service import AccessService, LoginService
from warehouse.bll.services.employee_service import EmployeeService


class Container(containers.DeclarativeContainer):
    """Граф зависимостей: инфраструктура, UnitOfWork и сервисы BLL."""

    config = providers.Configuration(default={"jwt_secret": None, "jwt_expire_minutes": 8 * 60})

    session_factory = providers.Object(scoped_session_factory)
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)

    access_service = providers.Factory(AccessService)
    login_service = providers.Factory(
        LoginService,
        uow=uow,
        access=access_service,
        secret_key=config.jwt_secret,
        expire_minutes=config.jwt_expire_minutes,
    )
    employee_service = providers.Factory(EmployeeService, uow_factory=uow.provider, access=access_service)

    query_service = providers.Factory(RouteQueryService, uow_factory=uow.provider, access=access_service)
    draft_service = providers.Factory(ShipmentDraftService, uow_factory=uow.provider, access=access_service)
    dispatch_service = providers.Factory(ShipmentDispatchService, uow_factory=uow.provider, access=access_service)
    transit_coordinator = providers.Factory(ShipmentTransitCoordinator)
    receive_service = providers.Factory(
        ShipmentReceiptService,
        uow_factory=uow.provider,
        access=access_service,
        transit=transit_coordinator,
    )

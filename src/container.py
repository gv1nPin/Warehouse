from dependency_injector import containers, providers

from warehouse.dal.database import scoped_session_factory
from warehouse.dal.unit_of_work import UnitOfWork

# Импортируем абсолютно все доменные сервисы BLL
from warehouse.bll.services.shipment_service import (
    ShipmentDraftService,
    ShipmentDispatchService,
    ShipmentReceiptService,
    RouteQueryService,
    ShipmentTransitCoordinator
)
from warehouse.bll.services.auth_service import AccessService, LoginService


class Container(containers.DeclarativeContainer):
    # Отключаем локальный wire, так как проклейка теперь вызывается из views.py
    # wiring_config = containers.WiringConfiguration(modules=["web.views"])

    # 1. Инфраструктура
    session_factory = providers.Object(scoped_session_factory)

    # 2. DAL: Unit of Work
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)

    # 3. BLL: Базовые сервисы авторизации
    access_service = providers.Factory(AccessService)
    login_service = providers.Factory(LoginService, uow=uow, access=access_service)
    
    # 4. BLL: Полный пакет сервисов Shipment (подключаем uow.provider как фабрику)
    query_service = providers.Factory(RouteQueryService, uow_factory=uow.provider, access=access_service)
    draft_service = providers.Factory(ShipmentDraftService, uow_factory=uow.provider, access=access_service)
    dispatch_service = providers.Factory(ShipmentDispatchService, uow_factory=uow.provider, access=access_service)
    
    # Сначала регистрируем координатор, так как он нужен сервису приемки грузов
    transit_coordinator = providers.Factory(ShipmentTransitCoordinator)
    
    receive_service = providers.Factory(
        ShipmentReceiptService, 
        uow_factory=uow.provider, 
        access=access_service,
        transit=transit_coordinator # Внедряем зависимость координатора в сервис приёмки
    )

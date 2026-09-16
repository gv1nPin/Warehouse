from dependency_injector import containers, providers
from Warehouse.DAL.Database import session_factory
from Warehouse.DAL.UnitOfWork import UnitOfWork

# Импортируем классы сервисов бизнес-логики BLL
from Warehouse.BLL.Services.AuthService.AuthService import AuthService
from Warehouse.BLL.Services.ShipmentService.ShipmentDispatchService import ShipmentDispatchService
from Warehouse.BLL.Services.ShipmentService.ShipmentTransitCoordinator import ShipmentTransitCoordinator
from Warehouse.BLL.Services.ShipmentService.ShipmentReceiptService import ShipmentReceiptService


class Container(containers.DeclarativeContainer):
    # Конфигурация явного wiring_config теперь расширена на роутеры и мапперы
    wiring_config = containers.WiringConfiguration(modules=[
        "main",
        "Warehouse.API.Auth",
        "Warehouse.API.Shipments",
        "Warehouse.API.Mappers.AuthMappers",
        "Warehouse.API.Mappers.ShipmentsMappers"
    ])

    # 1. Инфраструктурные зависимости (Фабрика сессий)
    session_factory = providers.Object(session_factory)

    # 2. DAL: Unit of Work 
    uow = providers.ThreadSafeSingleton(
        UnitOfWork,
        session_factory=session_factory,
    )

    # 3. BLL: Сервисы и координаторы
    auth_service = providers.Factory(
        AuthService,
        uow=uow,
    )

    dispatch_service = providers.Factory(
        ShipmentDispatchService,
        uow=uow,
    )

    transit_coordinator = providers.Factory(
        ShipmentTransitCoordinator,
        uow=uow,
        dispatch_service=dispatch_service,  
    )

    receipt_service = providers.Factory(
        ShipmentReceiptService,
        uow=uow,
        transit_coordinator=transit_coordinator,  
    )

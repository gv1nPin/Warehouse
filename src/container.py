from dependency_injector import containers, providers
from Warehouse.DAL.Database import session_factory

from Warehouse.DAL.UnitOfWork import UnitOfWork

# Импортируем сервисы бизнес-логики BLL
from Warehouse.BLL.Services.AuthService import AuthService # <-- ДОБАВЛЕНО
from Warehouse.BLL.Services.ShipmentService.ShipmentDispatchService import ShipmentDispatchService
from Warehouse.BLL.Services.ShipmentService.ShipmentTransitCoordinator import ShipmentTransitCoordinator
from Warehouse.BLL.Services.ShipmentService.ShipmentReceiptService import ShipmentReceiptService


class Container(containers.DeclarativeContainer):
    # Контейнер автоматически подтянет правильный путь к плагинам
    wiring_config = containers.WiringConfiguration(modules=["main"])

    # 1. Инфраструктурные зависимости (Фабрика сессий)
    session_factory = providers.Object(session_factory)

    # 2. DAL: Unit of Work 
    # ИСПРАВЛЕНО: ThreadSafeSingleton гарантирует, что все сервисы будут разделять 
    # ОДНУ И ТУ ЖЕ сессию SQLAlchemy и одну транзакцию в рамках выполнения операции.
    uow = providers.ThreadSafeSingleton(
        UnitOfWork,
        session_factory=session_factory,
    )

    # 3. BLL: Сервисы и координаторы
    
    # Добавлен сервис аутентификации (передаем в него синглтон uow)
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

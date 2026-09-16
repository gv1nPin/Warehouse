from dependency_injector import containers, providers
from warehouse.dal.database import session_factory

from warehouse.dal.unit_of_work import unit_of_work

from warehouse.bll.services.auth_service.auth_service import auth_service
from warehouse.bll.services.shipment_service.shipment_dispatch_service import shipment_dispatch_service
from warehouse.bll.services.shipment_service.shipment_transit_coordinator import shipment_transit_coordinator
from warehouse.bll.services.shipment_service.shipment_receipt_service import shipment_receipt_service


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

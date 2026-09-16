from dependency_injector import containers, providers

from Warehouse.DAL.database import session_factory
from Warehouse.DAL.unit_of_work import UnitOfWork


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(modules=["main"])

    # 1. Инфраструктура
    session_factory = providers.Object(session_factory)

    # 2. DAL: Unit of Work.
    # Factory, а не Singleton: у каждого сервиса свой UoW, и каждый `with uow:`
    # открывает свою сессию. Один общий UoW на всё приложение ломается,
    # как только два запроса идут одновременно.
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)

    # 3. BLL: сервисы добавляются сюда по мере готовности, например:
    # dispatch_service = providers.Factory(ShipmentDispatchService, uow=uow)

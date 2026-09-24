from dependency_injector import containers, providers

from warehouse.dal.database import scoped_session_factory
from warehouse.dal.unit_of_work import UnitOfWork
# импортируем сервисы БЛ, когда начнем их регистрировать
# from warehouse.bll.services.shipment_service import ShipmentDraftService
# from warehouse.bll.services.auth_service import AccessService


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(modules=["main"])

    # 1. Инфраструктура
    session_factory = providers.Object(scoped_session_factory)

    # 2. DAL: Unit of Work.
    # Factory, а не Singleton: у каждого сервиса свой UoW, и каждый `with uow:`
    # открывает свою сессию. Один общий UoW на всё приложение ломается,
    # как только два запроса идут одновременно.
    #
    # ФИКС: Передаем провайдер session_factory, а не сырой объект scoped_session_factory
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)

    # 3. BLL: сервисы добавляются сюда по мере готовности, например:
    # ФИКС типизации: ваши сервисы (ShipmentDraftService) на входе принимают uow_factory (Callable),
    # а провайдер Factory как раз ведет себя как Callable при инжекции в конструкторы других провайдеров.
    # 
    # access_service = providers.Factory(AccessService)
    # draft_service = providers.Factory(
    #     ShipmentDraftService, 
    #     uow_factory=uow.provider, # .provider передает фабрику как вызываемый объект (лямбду)
    #     access=access_service
    # )

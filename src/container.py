from dependency_injector import containers, providers

from warehouse.dal.database import scoped_session_factory
from warehouse.dal.unit_of_work import UnitOfWork
# импорты сервисов БЛ
from warehouse.bll.services.shipment_service import ShipmentDraftService
from warehouse.bll.services.auth_service import AccessService


class Container(containers.DeclarativeContainer):
    # ГАРАНТИЯ ИНЖЕКЦИИ: Указываем Django-модуль с вашими контроллерами
    wiring_config = containers.WiringConfiguration(modules=["warehouse.views"])

    # 1. Инфраструктура
    session_factory = providers.Object(scoped_session_factory)

    # 2. DAL: Unit of Work
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)

    # 3. BLL: Сервисы авторизации и черновиков
    access_service = providers.Factory(AccessService)
    
    draft_service = providers.Factory(
        ShipmentDraftService, 
        # Передаем фабрику UnitOfWork как Callable-объект (лямбду),
        # что строго соответствует вашему контракту `self._uow_factory()` в BLL
        uow_factory=uow.provider, 
        access=access_service
    )

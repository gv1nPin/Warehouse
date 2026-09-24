from dependency_injector import containers, providers

from warehouse.dal.database import scoped_session_factory
from warehouse.dal.unit_of_work import UnitOfWork
from warehouse.bll.services.shipment_service import ShipmentDraftService
from warehouse.bll.services.auth_service import AccessService

class Container(containers.DeclarativeContainer):
    # wiring_config = containers.WiringConfiguration(modules=["web.views"])
    
    session_factory = providers.Object(scoped_session_factory)
    uow = providers.Factory(UnitOfWork, session_factory=session_factory)
    access_service = providers.Factory(AccessService)
    draft_service = providers.Factory(
        ShipmentDraftService, uow_factory=uow.provider, access=access_service
    )

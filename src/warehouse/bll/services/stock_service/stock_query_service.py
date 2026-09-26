from collections.abc import Callable

from warehouse.bll.interfaces.auth_service import AbstractAccessService
from warehouse.bll.interfaces.stock_service import AbstractStockQueryService
from warehouse.common import PermissionName
from warehouse.common.dto import StockItemDTO
from warehouse.common.exceptions import AccessDeniedError
from warehouse.dal.unit_of_work import UnitOfWork

STOCK_PERMISSIONS = frozenset(
    {
        PermissionName.SHIPMENT_CREATE,
        PermissionName.SHIPMENT_DISPATCH,
        PermissionName.SHIPMENT_ACCEPT,
    }
)


class StockQueryService(AbstractStockQueryService):
    """Остатки склада для кладовщиков: на складе, в резерве, доступно."""

    def __init__(
        self, uow_factory: Callable[[], UnitOfWork], access: AbstractAccessService
    ) -> None:
        self._uow_factory = uow_factory
        self._access = access

    def list_stock(self, employee_id: int) -> list[StockItemDTO]:
        with self._uow_factory() as uow:
            actor = self._access.get_actor(uow, employee_id)
            if not actor.permissions & STOCK_PERMISSIONS:
                raise AccessDeniedError("Остатки видят только сотрудники склада")
            return uow.stock.list_by_warehouse(actor.employee.warehouse_id)

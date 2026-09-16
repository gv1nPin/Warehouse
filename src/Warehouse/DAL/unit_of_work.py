from sqlalchemy.orm import Session, sessionmaker

from .database import session_factory as default_session_factory
from .Repositories import (
    EmployeeRepository,
    MeasurementRepository,
    ProductRepository,
    RoleRepository,
    ShipmentRepository,
    ShipmentStageRepository,
    StageItemRepository,
    StatusRepository,
    StockRepository,
    WarehouseRepository,
)


class UnitOfWork:
    """Одна транзакция и все репозитории на ней.

    with uow:
        me = uow.employees.get_by_id(5)
        stages = uow.stages.list_for_warehouse(me.warehouse_id)

    При выходе без ошибок — commit, при исключении — rollback.
    Один объект можно использовать повторно: каждый `with` открывает новую сессию.
    """

    session: Session
    employees: EmployeeRepository
    roles: RoleRepository
    statuses: StatusRepository
    measurements: MeasurementRepository
    warehouses: WarehouseRepository
    products: ProductRepository
    stock: StockRepository
    shipments: ShipmentRepository
    stages: ShipmentStageRepository
    stage_items: StageItemRepository

    def __init__(self, session_factory: sessionmaker[Session] = default_session_factory):
        self._session_factory = session_factory

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.employees = EmployeeRepository(self.session)
        self.roles = RoleRepository(self.session)
        self.statuses = StatusRepository(self.session)
        self.measurements = MeasurementRepository(self.session)
        self.warehouses = WarehouseRepository(self.session)
        self.products = ProductRepository(self.session)
        self.stock = StockRepository(self.session)
        self.shipments = ShipmentRepository(self.session)
        self.stages = ShipmentStageRepository(self.session)
        self.stage_items = StageItemRepository(self.session)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

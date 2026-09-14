from sqlalchemy.orm import Session, sessionmaker

from .database import SessionLocal
from .Repositories import (
    EmployeeRepository,
    ReferenceRepository,
    ShipmentRepository,
    StockRepository,
    WarehouseRepository,
)


class UnitOfWork:
    """Одна транзакция и все репозитории на ней.

    with UnitOfWork() as uow:
        me = uow.employees.get_by_id(5)
        routes = uow.shipments.list_routes_for_warehouse(me.warehouse_id)

    При выходе без ошибок — commit, при исключении — rollback.
    """

    session: Session
    employees: EmployeeRepository
    warehouses: WarehouseRepository
    stock: StockRepository
    shipments: ShipmentRepository
    references: ReferenceRepository

    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal):
        self._session_factory = session_factory

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        self.employees = EmployeeRepository(self.session)
        self.warehouses = WarehouseRepository(self.session)
        self.stock = StockRepository(self.session)
        self.shipments = ShipmentRepository(self.session)
        self.references = ReferenceRepository(self.session)
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

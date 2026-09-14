# src/Warehouse.DAL/SQLAlchemyUnitOfWork.py
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Session
from src.Warehouse.DAL.Repositories import DispatchRepository, EmployeeRepository, ReceiptRepository, TransitRepository



class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._session: Optional[Session] = None
        
        # Объявляем публичные свойства репозиториев
        self.dispatch: Optional["DispatchRepository"] = None
        self.employee: Optional["EmployeeRepository"] = None
        self.receipt: Optional["ReceiptRepository"] = None
        self.transit: Optional["TransitRepository"] = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Сессия не инициализирована. Используйте 'with uow:'.")
        return self._session

    def __enter__(self):
        self._session = self.session_factory()
        
        # Инициализируем репозитории и передаем им текущий UOW
        self.dispatch = DispatchRepository(self)
        self.employee = EmployeeRepository(self)
        self.receipt = ReceiptRepository(self)
        self.transit = TransitRepository(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self._session.rollback()
            else:
                self._session.commit()
        finally:
            self._session.close()
            self._session = None
            
            # Очищаем ссылки на репозитории после закрытия сессии
            self.dispatch = None
            self.employee = None
            self.receipt = None
            self.transit = None

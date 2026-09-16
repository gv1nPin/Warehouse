from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from Warehouse.DAL.Repositories.DispatchRepository import DispatchRepository
    from Warehouse.DAL.Repositories.EmployeeRepository import EmployeeRepository
    from Warehouse.DAL.Repositories.ReceiptRepository import ReceiptRepository
    from Warehouse.DAL.Repositories.TransitRepository import TransitRepository
    from Warehouse.DAL.Repositories.HistoryRepository import HistoryRepository  # Добавлено для аннотации типов


class UnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._session: Optional[Session] = None
        
        # Объявляем публичные свойства репозиториев
        self.dispatch: Optional["DispatchRepository"] = None
        self.employee: Optional["EmployeeRepository"] = None
        self.receipt: Optional["ReceiptRepository"] = None
        self.transit: Optional["TransitRepository"] = None
        self.history: Optional["HistoryRepository"] = None  # Добавлено свойство репозитория аудита

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Сессия не инициализирована. Используйте 'with uow:'.")
        return self._session

    def __enter__(self):
        self._session = self.session_factory()
        
        # Локальный импорт классов репозиториев в рантайме для исключения циклических зависимостей
        from Warehouse.DAL.Repositories.DispatchRepository import DispatchRepository
        from Warehouse.DAL.Repositories.EmployeeRepository import EmployeeRepository
        from Warehouse.DAL.Repositories.ReceiptRepository import ReceiptRepository
        from Warehouse.DAL.Repositories.TransitRepository import TransitRepository
        from Warehouse.DAL.Repositories.HistoryRepository import HistoryRepository  # Добавлено локально
        
        # Инициализируем репозитории и передаем им текущий экземпляр UOW
        self.dispatch = DispatchRepository(self)
        self.employee = EmployeeRepository(self)
        self.receipt = ReceiptRepository(self)
        self.transit = TransitRepository(self)
        self.history = HistoryRepository(self)  # Инициализируем репозиторий истории операций
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
            self.history = None  # Очищаем ссылку на репозиторий аудита

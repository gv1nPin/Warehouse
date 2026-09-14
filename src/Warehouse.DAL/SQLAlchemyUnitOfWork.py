from typing import Optional
from sqlalchemy.orm import Session

class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._session: Optional[Session] = None

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("Сессия не инициализирована. Используйте 'with uow:'.")
        return self._session

    def __enter__(self):
        self._session = self.session_factory()
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


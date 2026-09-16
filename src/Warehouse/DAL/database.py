import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
# загружается env.example
load_dotenv()

DATABASE_URL = URL.create(
    drivername="postgresql+psycopg2",
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "Warehouse"),
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Наш контекстный менеджер
@contextmanager
def get_session():
    """Контекстный менеджер для безопасной работы с сессией SQLAlchemy."""
    session: Session = session_factory()
    try:
        yield session
        session.commit()  # Автоматически делаем коммит, если всё прошло успешно
    except Exception:
        session.rollback()  # Откатываем транзакцию при любой ошибке
        raise  # Пробрасываем ошибку дальше для логирования или обработки в BLL
    finally:
        session.close()  # Гарантированно закрываем сессию и возвращаем коннект в пул

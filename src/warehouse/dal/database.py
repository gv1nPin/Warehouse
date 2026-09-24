import os
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker, scoped_session

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
    pool_pre_ping=True,
    pool_size=10,       # Настройка пула под нагрузку Django
    max_overflow=20
)

# Фабрика сессий
_session_factory = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False
)

# scoped_session связывает сессию с текущим потоком выполнения (Thread-local)
# Именно её будет использовать UnitOfWork
scoped_session_factory = scoped_session(_session_factory)

import os
from sqlalchemy import create_engine

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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

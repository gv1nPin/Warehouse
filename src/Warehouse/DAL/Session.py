import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:1234@localhost:5432/warehouse_db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

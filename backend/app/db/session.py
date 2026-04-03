from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+aiomysql://radius:radiuspassword@localhost/radius"
)

engine = create_async_engine(
    DATABASE_URL, echo=os.getenv("SQL_ECHO", "false").lower() == "true"
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db():
    async with SessionLocal() as session:
        yield session

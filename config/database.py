import os
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from shared.sqlalchemy_metrics import register_sqlalchemy_metrics

DATABASE_URL = os.environ["DATABASE_URL"]
ASYNC_DATABASE_URL = os.environ["ASYNC_DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
)
register_sqlalchemy_metrics(engine, pool="sync")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=1800,
)
register_sqlalchemy_metrics(async_engine.sync_engine, pool="async")
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with AsyncSessionLocal() as db:
        yield db

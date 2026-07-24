from collections.abc import AsyncGenerator
from typing import Protocol

from fastapi import Request
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def create_engine(database_url_async: str, *, connect_timeout: float) -> AsyncEngine:
    return create_async_engine(
        database_url_async,
        pool_pre_ping=True,
        connect_args={"timeout": connect_timeout},
    )


def create_session_maker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker[AsyncSession](engine, class_=AsyncSession, expire_on_commit=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession]:
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker
    async with session_maker() as session:
        yield session


def load_model_metadata() -> None:
    import app.modules.auth.infrastructure.sqlalchemy_models  # noqa: F401
    import app.modules.users.infrastructure.sqlalchemy_models  # noqa: F401


async def create_tables(engine: AsyncEngine) -> None:
    load_model_metadata()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_user_profiles_phone_columns)


def _ensure_user_profiles_phone_columns(connection) -> None:
    inspector = inspect(connection)
    if "user_profiles" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("user_profiles")}
    missing_columns = {
        "country_code": "VARCHAR(2)",
        "dial_code": "VARCHAR(8)",
        "phone_number": "VARCHAR(32)",
    }.items()
    for name, column_type in missing_columns:
        if name not in columns:
            connection.execute(text(f"ALTER TABLE user_profiles ADD COLUMN {name} {column_type}"))

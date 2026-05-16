from collections.abc import AsyncGenerator
from typing import Protocol

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


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
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker
    async with session_maker() as session:
        yield session


async def apply_postgresql_schema_patches(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(32)"))
        await conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
        await conn.execute(text("UPDATE users SET status = 'active' WHERE status IS NULL"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'active'"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN role SET NOT NULL"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN status SET NOT NULL"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users (status)"))


def load_model_metadata() -> None:
    import app.modules.auth.infrastructure.sqlalchemy_models  # noqa: F401
    import app.modules.users.infrastructure.sqlalchemy_models  # noqa: F401


async def create_tables(engine: AsyncEngine) -> None:
    load_model_metadata()
    settings = get_settings()
    async with engine.begin() as conn:
        if settings.database_reset_schema:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await apply_postgresql_schema_patches(engine)

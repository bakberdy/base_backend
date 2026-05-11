from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.pg_patches import apply_postgresql_schema_patches, load_model_metadata


def create_engine(database_url_async: str, *, connect_timeout: float):
    return create_async_engine(
        database_url_async,
        pool_pre_ping=True,
        connect_args={"timeout": connect_timeout},
    )


def create_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_maker: async_sessionmaker[AsyncSession] = request.app.state.session_maker
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables(engine) -> None:
    load_model_metadata()
    settings = get_settings()

    async with engine.begin() as conn:
        if settings.database_reset_schema:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    await apply_postgresql_schema_patches(engine)

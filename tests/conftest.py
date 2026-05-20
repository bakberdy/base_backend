import os
import asyncio
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

os.environ.setdefault("ENVIRONMENT", "development")


def pytest_configure() -> None:
    pytest.register_assert_rewrite("tests.helpers")


def _integration_tests_enabled() -> bool:
    return os.environ.get("RUN_INTEGRATION_TESTS") == "1"


def _database_reset_allowed(postgres_db: str) -> bool:
    if os.environ.get("ALLOW_INTEGRATION_DB_RESET") == "1":
        return True
    return "test" in postgres_db.lower()


async def _assert_database_ready(database_url_async: str, connect_timeout: float) -> None:
    from app.core.database import create_engine

    engine = create_engine(database_url_async, connect_timeout=connect_timeout)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def _assert_redis_ready(redis_url: str) -> None:
    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url, decode_responses=False)
    try:
        await redis.ping()
    finally:
        await redis.aclose()


async def _reset_redis(redis_url: str) -> None:
    from redis.asyncio import Redis

    redis = Redis.from_url(redis_url, decode_responses=False)
    try:
        await redis.flushdb()
    finally:
        await redis.aclose()


async def _reset_database(database_url_async: str, connect_timeout: float) -> None:
    from app.core.database import (
        Base,
        create_engine,
        load_model_metadata,
    )

    engine = create_engine(database_url_async, connect_timeout=connect_timeout)
    try:
        load_model_metadata()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def integration_settings() -> Any:
    if not _integration_tests_enabled():
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")

    from app.core.config import get_settings

    settings = get_settings()
    if not _database_reset_allowed(settings.postgres_db):
        pytest.skip(
            "Integration tests reset database tables. Use a test database name "
            "or set ALLOW_INTEGRATION_DB_RESET=1 explicitly."
        )

    try:
        asyncio.run(
            _assert_database_ready(
                settings.database_url_async,
                settings.database_connect_timeout,
            ),
        )
    except Exception as exc:
        pytest.skip(f"PostgreSQL integration database is not reachable: {exc}")

    try:
        asyncio.run(_assert_redis_ready(settings.redis_url))
    except Exception as exc:
        pytest.skip(f"Redis integration store is not reachable: {exc}")

    return settings


@pytest.fixture()
def integration_session_maker(
    integration_settings: Any,
) -> Generator[async_sessionmaker[AsyncSession], None, None]:
    from app.core.database import create_engine, create_session_maker

    asyncio.run(
        _reset_database(
            integration_settings.database_url_async,
            integration_settings.database_connect_timeout,
        ),
    )
    asyncio.run(_reset_redis(integration_settings.redis_url))
    engine = create_engine(
        integration_settings.database_url_async,
        connect_timeout=integration_settings.database_connect_timeout,
    )
    try:
        yield create_session_maker(engine)
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture()
def integration_client(integration_settings: Any) -> Generator[TestClient, None, None]:
    from app.main import create_app
    from app.core.security import limiter

    asyncio.run(
        _reset_database(
            integration_settings.database_url_async,
            integration_settings.database_connect_timeout,
        ),
    )
    asyncio.run(_reset_redis(integration_settings.redis_url))
    limiter.reset()
    application = create_app()
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client

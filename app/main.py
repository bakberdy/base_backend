from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import HTTPExceptionHandler

from app.api.error_handlers import register_exception_handlers
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.session import create_engine, create_session_maker, create_tables
from app.modules.auth import router as auth_router
from app.modules.users.router import router as users_router
from app.openapi import configure_openapi


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


rate_limit_handler: HTTPExceptionHandler = rate_limit_exceeded_handler


def _pg_endpoint_hint(dsn: str) -> str:
    parsed = urlparse(dsn)
    host = parsed.hostname or "(no host)"
    port = parsed.port or 5432
    return f"{host}:{port}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_engine(
        settings.database_url_async,
        connect_timeout=settings.database_connect_timeout,
    )
    try:
        await create_tables(engine)
    except TimeoutError as exc:
        await engine.dispose()
        target = _pg_endpoint_hint(settings.database_url)
        raise RuntimeError(
            f"Timed out connecting to PostgreSQL at {target} after "
            f"{settings.database_connect_timeout}s. "
            "Ensure Postgres is up (`docker compose up -d`), port 5432 is free, and "
            "try DATABASE_URL with host 127.0.0.1 instead of localhost."
        ) from exc
    except (ConnectionRefusedError, OSError) as exc:
        await engine.dispose()
        target = _pg_endpoint_hint(settings.database_url)
        raise RuntimeError(
            f"Cannot reach PostgreSQL at {target} (connection refused). "
            "Start the database first, e.g. from the project root: `docker compose up -d`, "
            "then run uvicorn again."
        ) from exc

    app.state.engine = engine
    app.state.session_maker = create_session_maker(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=f"Mobile app API ({settings.app_env})",
        description=f"Environment: **{settings.app_env}**.",
        lifespan=lifespan,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_exception_handlers(application)
    application.include_router(auth_router)
    application.include_router(users_router)
    configure_openapi(application)
    return application


app = create_app()

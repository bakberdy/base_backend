import socket
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
from app.core.i18n import locale_from_request, reset_locale, set_locale
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


def _connection_refused_hint(dsn: str) -> str:
    hostname = urlparse(dsn).hostname
    if hostname in ("127.0.0.1", "localhost", "::1"):
        return (
            "Nothing is listening there yet. From mobile_app_backend run "
            "`docker compose up -d postgres`, wait until "
            "the container is healthy, then start uvicorn again."
        )
    return (
        "Ensure Postgres is running. For uvicorn on the host use POSTGRES_HOST=127.0.0.1; "
        "inside Docker Compose the api service uses hostname `postgres`."
    )


def _caused_by_dns_failure(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, socket.gaierror):
            return True
        current = current.__cause__
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    dsn = settings.database_url
    target = _pg_endpoint_hint(dsn)
    engine = create_engine(
        settings.database_url_async,
        connect_timeout=settings.database_connect_timeout,
    )
    try:
        await create_tables(engine)
    except TimeoutError as exc:
        await engine.dispose()
        raise RuntimeError(
            f"Timed out connecting to PostgreSQL at {target} after "
            f"{settings.database_connect_timeout}s. "
            "Ensure Postgres is up (`docker compose up -d`), port 5432 is free, and "
            "try DATABASE_URL with host 127.0.0.1 instead of localhost."
        ) from exc
    except ConnectionRefusedError as exc:
        await engine.dispose()
        hint = _connection_refused_hint(dsn)
        raise RuntimeError(
            f"Cannot reach PostgreSQL at {target} (connection refused). {hint}"
        ) from exc
    except OSError as exc:
        await engine.dispose()
        if _caused_by_dns_failure(exc):
            raise RuntimeError(
                f"Could not resolve PostgreSQL host at {target}. "
                "The hostname `postgres` only works inside Docker's network. "
                "For local uvicorn use POSTGRES_HOST=127.0.0.1; "
                "inside Docker Compose use POSTGRES_HOST=postgres."
            ) from exc
        raise RuntimeError(
            f"Cannot reach PostgreSQL at {target}: {exc}. "
            "Ensure Postgres is running and POSTGRES_HOST matches how you run the app "
            "(127.0.0.1 on the host, service name inside Compose)."
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

    @application.middleware("http")
    async def locale_middleware(request: Request, call_next):
        token = set_locale(locale_from_request(request))
        try:
            return await call_next(request)
        finally:
            reset_locale(token)

    application.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_exception_handlers(application)
    application.include_router(auth_router)
    application.include_router(users_router)
    configure_openapi(application)
    return application


app = create_app()

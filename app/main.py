from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import Redis
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import HTTPExceptionHandler

from app.common.exceptions.handlers import register_exception_handlers
from app.core.config import get_settings
from app.core.database import create_engine, create_session_maker, create_tables
from app.core.logging import configure_logging
from app.core.middleware import configure_openapi, register_middlewares
from app.core.security import limiter
from app.modules.auth.api.router import router as auth_router
from app.modules.users.api.router import router as users_router


def rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return _rate_limit_exceeded_handler(request, exc)


rate_limit_handler: HTTPExceptionHandler = rate_limit_exceeded_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    dsn = settings.database_url
    target = dsn
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
            "try DATABASE_URL with host 127.0.0.1 when running the API on the host."
        ) from exc
    except ConnectionRefusedError as exc:
        await engine.dispose()
        raise RuntimeError(
            f"Cannot reach PostgreSQL at {target} (connection refused)."
        ) from exc
    except OSError as exc:
        await engine.dispose()
        raise RuntimeError(
            f"Cannot reach PostgreSQL at {target}: {exc}."
        ) from exc
    app.state.engine = engine
    app.state.session_maker = create_session_maker(engine)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=False)
    yield
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    application = FastAPI(
        title=f"Mobile app API ({settings.environment})",
        description=(
            f"Environment: **{settings.environment}**.\n\n"
            "Localized responses support `en`, `kk`, and `ru` through the "
            "`Accept-Language` header."
        ),
        lifespan=lifespan,
    )
    application.state.limiter = limiter

    @application.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    application.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    register_middlewares(
        application,
        cors_allowed_origins=settings.cors_origins,
        cors_allow_credentials=settings.cors_allow_credentials,
    )
    register_exception_handlers(application)
    application.include_router(auth_router)
    application.include_router(users_router)
    configure_openapi(application)
    return application


app = create_app()

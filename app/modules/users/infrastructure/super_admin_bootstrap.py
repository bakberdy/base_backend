import asyncio
import os

from redis.asyncio import Redis

from app.common.authorization.redis_store import RedisAccessStateStore
from app.core.config import get_settings
from app.core.database import (
    SqlAlchemyUnitOfWork,
    create_engine,
    create_session_maker,
    create_tables,
)
from app.modules.users.application.use_cases.bootstrap_super_admin import (
    BootstrapSuperAdminUseCase,
)
from app.modules.users.infrastructure.sqlalchemy_repositories import (
    SqlAlchemyUserRepository,
)


async def bootstrap_super_admin() -> None:
    email = os.environ.get("SUPER_ADMIN_EMAIL", "").strip()
    if not email:
        raise RuntimeError("SUPER_ADMIN_EMAIL is required")

    settings = get_settings()
    engine = create_engine(
        settings.database_url_async,
        connect_timeout=settings.database_connect_timeout,
    )
    redis = Redis.from_url(settings.redis_url, decode_responses=False)
    try:
        await create_tables(engine)
        session_maker = create_session_maker(engine)
        async with session_maker() as session:
            use_case = BootstrapSuperAdminUseCase(
                SqlAlchemyUserRepository(session),
                RedisAccessStateStore(redis),
                SqlAlchemyUnitOfWork(session),
            )
            user = await use_case.execute(email)
            print(f"SUPER_ADMIN_BOOTSTRAP_STATUS=success user_id={user.id}")
    finally:
        await redis.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(bootstrap_super_admin())


if __name__ == "__main__":
    main()

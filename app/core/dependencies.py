from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.authorization.redis_store import RedisAccessStateStore
from app.common.authorization.repositories import (
    AccessStateStore,
    AuthorizationIdentityRepository,
    SessionRevocationRepository,
)
from app.core.database import get_db
from app.core.redis import get_redis
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.infrastructure.sqlalchemy_repositories import SqlAlchemyAuthRepository
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.sqlalchemy_repositories import SqlAlchemyUserRepository


def get_auth_repository(session: AsyncSession = Depends(get_db)) -> AuthRepository:
    return SqlAlchemyAuthRepository(session)


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_authorization_identity_repository(
    session: AsyncSession = Depends(get_db),
) -> AuthorizationIdentityRepository:
    return SqlAlchemyUserRepository(session)


def get_session_revocation_repository(
    session: AsyncSession = Depends(get_db),
) -> SessionRevocationRepository:
    return SqlAlchemyAuthRepository(session)


def get_access_state_store(redis: Redis = Depends(get_redis)) -> AccessStateStore:
    return RedisAccessStateStore(redis)

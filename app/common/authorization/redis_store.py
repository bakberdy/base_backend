from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.common.authorization.entities import CachedAccessState
from app.common.authorization.repositories import AccessStateStore
from app.common.exceptions.base import DependencyUnavailableError, InvalidDependencyStateError


def _user_version_key(user_id: UUID) -> str:
    return f"authz:user:{user_id}:version"


def _user_sessions_key(user_id: UUID) -> str:
    return f"auth:user:{user_id}:sessions"


def _session_key(session_id: UUID) -> str:
    return f"auth:session:{session_id}"


_SET_VERSION_IF_GREATER = """
local current = redis.call('GET', KEYS[1])
if not current or tonumber(ARGV[1]) > tonumber(current) then
    redis.call('SET', KEYS[1], ARGV[1])
    return ARGV[1]
end
return current
"""


class RedisAccessStateStore(AccessStateStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self, user_id: UUID, session_id: UUID) -> CachedAccessState:
        try:
            values = await self._redis.mget(
                _user_version_key(user_id),
                _session_key(session_id),
            )
        except RedisError as exc:
            raise DependencyUnavailableError("redis") from exc

        raw_version, raw_session_user_id = values
        try:
            authorization_version = int(raw_version) if raw_version is not None else None
        except (TypeError, ValueError) as exc:
            raise InvalidDependencyStateError("redis") from exc

        if raw_session_user_id is None:
            session_active = None
        else:
            value = (
                raw_session_user_id.decode("utf-8")
                if isinstance(raw_session_user_id, bytes)
                else str(raw_session_user_id)
            )
            session_active = value == str(user_id)

        return CachedAccessState(authorization_version, session_active)

    async def cache(
        self,
        *,
        user_id: UUID,
        authorization_version: int,
        session_id: UUID,
        session_expires_at: datetime,
    ) -> None:
        now = datetime.now(UTC)
        ttl_seconds = max(1, int((session_expires_at - now).total_seconds()))
        sessions_key = _user_sessions_key(user_id)
        try:
            await self._set_authorization_version_if_greater(
                user_id,
                authorization_version,
            )
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(_session_key(session_id), str(user_id), ex=ttl_seconds)
                pipe.zremrangebyscore(sessions_key, 0, now.timestamp())
                pipe.zadd(sessions_key, {str(session_id): session_expires_at.timestamp()})
                await pipe.execute()
        except RedisError as exc:
            raise DependencyUnavailableError("redis") from exc

    async def set_authorization_version(self, user_id: UUID, version: int) -> None:
        try:
            await self._set_authorization_version_if_greater(user_id, version)
        except RedisError as exc:
            raise DependencyUnavailableError("redis") from exc

    async def _set_authorization_version_if_greater(
        self,
        user_id: UUID,
        version: int,
    ) -> None:
        await cast(
            Awaitable[object],
            self._redis.eval(
                _SET_VERSION_IF_GREATER,
                1,
                _user_version_key(user_id),
                str(version),
            ),
        )

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> None:
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(_session_key(session_id))
                pipe.zrem(_user_sessions_key(user_id), str(session_id))
                await pipe.execute()
        except RedisError as exc:
            raise DependencyUnavailableError("redis") from exc

    async def revoke_all_sessions(self, user_id: UUID) -> None:
        sessions_key = _user_sessions_key(user_id)
        try:
            session_ids = await cast(
                Awaitable[list[str | bytes]],
                self._redis.zrange(sessions_key, 0, -1),
            )
            keys = [
                _session_key(UUID(value.decode() if isinstance(value, bytes) else value))
                for value in session_ids
            ]
            async with self._redis.pipeline(transaction=True) as pipe:
                if keys:
                    pipe.delete(*keys)
                pipe.delete(sessions_key)
                await pipe.execute()
        except (RedisError, ValueError) as exc:
            if isinstance(exc, RedisError):
                raise DependencyUnavailableError("redis") from exc
            raise InvalidDependencyStateError("redis") from exc

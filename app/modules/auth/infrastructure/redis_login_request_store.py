import json
from datetime import UTC, datetime
from typing import Any, Awaitable, cast
from uuid import UUID

from redis.asyncio import Redis

from app.modules.auth.domain.entities import LoginRequest
from app.modules.auth.domain.repositories import LoginRequestStore


class RedisLoginRequestStore(LoginRequestStore):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def delete_pending_logins(self, user_id: UUID, user_device_id: UUID) -> None:
        pending_key = _pending_key(user_id, user_device_id)
        request_ids = await cast(Awaitable[set[str | bytes]], self._redis.smembers(pending_key))
        if request_ids:
            keys = [_request_key(_decode_id(request_id)) for request_id in request_ids]
            await self._redis.delete(*keys)
        await self._redis.delete(pending_key)

    async def create_login_request(
        self,
        *,
        request_id: str,
        user_id: UUID,
        user_device_id: UUID,
        otp_hash: str,
        attempts_left: int,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        ttl = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        payload = {
            "id": request_id,
            "user_id": str(user_id),
            "user_device_id": str(user_device_id),
            "otp_hash": otp_hash,
            "attempts_left": attempts_left,
            "expires_at": expires_at.isoformat(),
            "created_at": created_at.isoformat(),
            "consumed_at": None,
        }
        request_key = _request_key(request_id)
        pending_key = _pending_key(user_id, user_device_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(request_key, json.dumps(payload), ex=ttl)
            pipe.sadd(pending_key, request_id)
            pipe.expire(pending_key, ttl)
            await pipe.execute()

    async def get_login_request(self, request_id: str) -> LoginRequest | None:
        raw = await self._redis.get(_request_key(request_id))
        if raw is None:
            return None
        data = json.loads(_decode_id(raw))
        return LoginRequest(
            id=str(data["id"]),
            user_id=UUID(str(data["user_id"])),
            user_device_id=UUID(str(data["user_device_id"])),
            otp_hash=str(data["otp_hash"]),
            attempts_left=int(data["attempts_left"]),
            expires_at=datetime.fromisoformat(str(data["expires_at"])),
            consumed_at=_parse_optional_datetime(data.get("consumed_at")),
        )

    async def mark_login_consumed(self, request_id: str, consumed_at: datetime) -> None:
        await self._patch_request(request_id, {"consumed_at": consumed_at.isoformat()})

    async def update_login_attempts(self, request_id: str, attempts_left: int) -> None:
        await self._patch_request(request_id, {"attempts_left": attempts_left})

    async def delete_login_request(self, request_id: str) -> None:
        login_request = await self.get_login_request(request_id)
        await self._redis.delete(_request_key(request_id))
        if login_request is not None:
            await cast(
                Awaitable[Any],
                self._redis.srem(_pending_key(login_request.user_id, login_request.user_device_id), request_id),
            )

    async def _patch_request(self, request_id: str, values: dict[str, object]) -> None:
        key = _request_key(request_id)
        raw = await self._redis.get(key)
        if raw is None:
            return
        ttl = await self._redis.ttl(key)
        data = json.loads(_decode_id(raw))
        data.update(values)
        await self._redis.set(key, json.dumps(data), ex=max(1, ttl))


def _request_key(request_id: str) -> str:
    return f"login_request:{request_id}"


def _pending_key(user_id: UUID, user_device_id: UUID) -> str:
    return f"login_request_pending:{user_id}:{user_device_id}"


def _decode_id(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value


def _parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))

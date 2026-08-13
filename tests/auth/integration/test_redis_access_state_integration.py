import asyncio
from typing import Any
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.common.authorization.redis_store import RedisAccessStateStore

pytestmark = pytest.mark.integration


def test_authorization_version_never_moves_backwards(integration_settings: Any) -> None:
    async def scenario() -> None:
        redis = Redis.from_url(integration_settings.redis_url, decode_responses=False)
        user_id = uuid4()
        try:
            store = RedisAccessStateStore(redis)
            await store.set_authorization_version(user_id, 5)
            await store.set_authorization_version(user_id, 3)

            state = await store.get(user_id, uuid4())

            assert state.authorization_version == 5
            assert state.session_active is None
        finally:
            await redis.delete(f"authz:user:{user_id}:version")
            await redis.aclose()

    asyncio.run(scenario())

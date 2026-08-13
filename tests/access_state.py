from datetime import datetime
from uuid import UUID

from app.common.authorization.entities import CachedAccessState


class AccessStateStoreSpy:
    def __init__(self, cached: CachedAccessState | None = None) -> None:
        self.cached = cached or CachedAccessState(None, None)
        self.cached_sessions: list[tuple[UUID, int, UUID, datetime]] = []
        self.versions: list[tuple[UUID, int]] = []
        self.revoked_sessions: list[tuple[UUID, UUID]] = []
        self.revoked_users: list[UUID] = []

    async def get(self, user_id: UUID, session_id: UUID) -> CachedAccessState:
        return self.cached

    async def cache(
        self,
        *,
        user_id: UUID,
        authorization_version: int,
        session_id: UUID,
        session_expires_at: datetime,
    ) -> None:
        self.cached_sessions.append(
            (user_id, authorization_version, session_id, session_expires_at)
        )

    async def set_authorization_version(self, user_id: UUID, version: int) -> None:
        self.versions.append((user_id, version))

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> None:
        self.revoked_sessions.append((user_id, session_id))

    async def revoke_all_sessions(self, user_id: UUID) -> None:
        self.revoked_users.append(user_id)

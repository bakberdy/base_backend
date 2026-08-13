from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.authorization.entities import AuthorizationIdentity, CachedAccessState


class AuthorizationIdentityRepository(Protocol):
    async def get_by_email(self, email: str) -> AuthorizationIdentity | None: ...

    async def get_by_id(self, user_id: UUID) -> AuthorizationIdentity | None: ...

    async def get_or_create(self, email: str, now: datetime) -> AuthorizationIdentity: ...

    async def set_verified(self, user_id: UUID, value: bool) -> None: ...


class AccessStateStore(Protocol):
    async def get(self, user_id: UUID, session_id: UUID) -> CachedAccessState: ...

    async def cache(
        self,
        *,
        user_id: UUID,
        authorization_version: int,
        session_id: UUID,
        session_expires_at: datetime,
    ) -> None: ...

    async def set_authorization_version(self, user_id: UUID, version: int) -> None: ...

    async def revoke_session(self, user_id: UUID, session_id: UUID) -> None: ...

    async def revoke_all_sessions(self, user_id: UUID) -> None: ...


class SessionRevocationRepository(Protocol):
    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...

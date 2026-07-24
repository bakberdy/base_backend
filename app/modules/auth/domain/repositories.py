from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.pagination.schemas import SortingMethod
from app.modules.auth.domain.entities import DeviceInfo, LoginRequest, UserSession


class AuthRepository(Protocol):
    async def lock_user_refresh(self, user_id: UUID) -> None: ...

    async def upsert_user_device(
        self, *, user_id: UUID, device: DeviceInfo, now: datetime
    ) -> UUID: ...

    async def update_user_device_notifications(
        self,
        *,
        user_device_id: UUID,
        push_provider: str | None,
        push_token: str | None,
        now: datetime,
    ) -> None: ...

    async def touch_user_device(self, user_device_id: UUID, at: datetime) -> None: ...

    async def revoke_active_sessions_for_user_device(
        self, user_id: UUID, user_device_id: UUID, revoked_at: datetime
    ) -> None: ...

    async def create_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        user_device_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        created_at: datetime,
        last_active_at: datetime,
    ) -> None: ...

    async def get_session(self, session_id: UUID) -> UserSession | None: ...

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None: ...

    async def count_sessions_for_user(
        self, user_id: UUID, *, is_active: bool | None = None
    ) -> int: ...

    async def list_sessions_for_user(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        is_active: bool | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[UserSession]: ...

    async def revoke_session(
        self, session_id: UUID, user_id: UUID, revoked_at: datetime
    ) -> bool: ...

    async def revoke_session_by_id(self, session_id: UUID, revoked_at: datetime) -> None: ...

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None: ...

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None: ...


class LoginRequestStore(Protocol):
    async def delete_pending_logins(self, user_id: UUID, user_device_id: UUID) -> None: ...

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
    ) -> None: ...

    async def get_login_request(self, request_id: str) -> LoginRequest | None: ...

    async def mark_login_consumed(self, request_id: str, consumed_at: datetime) -> None: ...

    async def update_login_attempts(self, request_id: str, attempts_left: int) -> None: ...

    async def delete_login_request(self, request_id: str) -> None: ...

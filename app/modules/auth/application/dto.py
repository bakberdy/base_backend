from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.pagination.schemas import PaginationMeta
from app.modules.auth.domain.entities import DeviceInfo, DeviceNotifications, UserSession


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@dataclass(slots=True)
class LoginResultDto:
    message_code: str
    login_request_id: str
    otp_expires_in: int


@dataclass(slots=True)
class TokenPairDto:
    access_token: str
    refresh_token: str


@dataclass(slots=True)
class DeviceDto:
    id: UUID
    client_device_id: str
    os: str
    os_version: str
    model: str
    app_version: str
    push_provider: str | None
    has_notification_token: bool


@dataclass(slots=True)
class SessionDto:
    id: UUID
    user_id: UUID
    refresh_token_hash: str
    device: DeviceDto
    created_at: datetime
    expires_at: datetime
    last_active: datetime
    revoked_at: datetime | None
    is_revoked: bool

    @classmethod
    def from_entity(cls, session: UserSession) -> "SessionDto":
        if session.user_device is None:
            raise ValueError("session.user_device is required")
        return cls(
            id=session.id,
            user_id=session.user_id,
            refresh_token_hash=session.refresh_token_hash,
            device=DeviceDto(
                id=session.user_device.id,
                client_device_id=session.user_device.client_device_id,
                os=session.user_device.os,
                os_version=session.user_device.os_version,
                model=session.user_device.model,
                app_version=session.user_device.app_version,
                push_provider=session.user_device.push_provider,
                has_notification_token=session.user_device.push_token is not None,
            ),
            created_at=session.created_at,
            expires_at=session.expires_at,
            last_active=session.last_active_at,
            revoked_at=session.revoked_at,
            is_revoked=session.revoked_at is not None,
        )


@dataclass(slots=True)
class SessionsPageDto:
    items: list[SessionDto]
    pagination: PaginationMeta


@dataclass(slots=True)
class MessageResultDto:
    message_code: str


__all__ = [
    "DeviceInfo",
    "DeviceNotifications",
    "LoginResultDto",
    "MessageResultDto",
    "SessionsPageDto",
    "SessionDto",
    "TokenPairDto",
]

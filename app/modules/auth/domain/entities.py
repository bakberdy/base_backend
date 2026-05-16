from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class DeviceInfo:
    device_id: str
    os: str
    os_version: str
    model: str
    app_version: str
    push_provider: str | None = None
    push_token: str | None = None


@dataclass(slots=True)
class DeviceNotifications:
    push_provider: str | None = None
    push_token: str | None = None


@dataclass(slots=True)
class UserDevice:
    id: UUID
    client_device_id: str
    os: str
    os_version: str
    model: str
    app_version: str
    push_provider: str | None
    push_token: str | None


@dataclass(slots=True)
class LoginRequest:
    id: str
    user_id: UUID
    user_device_id: UUID
    otp_hash: str
    attempts_left: int
    expires_at: datetime
    consumed_at: datetime | None


@dataclass(slots=True)
class UserSession:
    id: UUID
    user_id: UUID
    user_device_id: UUID
    refresh_token_hash: str
    expires_at: datetime
    created_at: datetime
    last_active_at: datetime
    revoked_at: datetime | None
    user_device: UserDevice | None = None

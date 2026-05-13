from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.models import UserSession


from app.schemas.error import ErrorDetails, ErrorType


class DeviceInfo(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., max_length=64)
    os_version: str = Field(..., max_length=64)
    model: str = Field(..., max_length=128)
    app_version: str = Field(..., max_length=64)
    push_provider: str | None = Field(None, max_length=32)
    push_token: str | None = Field(None, max_length=4096)


class LoginBody(BaseModel):
    email: EmailStr
    device: DeviceInfo


class LoginResponse(BaseModel):
    message: str
    login_request_id: str
    otp_expires_in: int


class VerifyBody(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    login_request_id: str = Field(..., min_length=1, max_length=64)


class VerifyResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshBody(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class DeviceNotificationsBody(BaseModel):
    push_provider: str | None = Field(None, max_length=32)
    push_token: str | None = Field(None, max_length=4096)


class DeviceNotificationsResponse(BaseModel):
    pass


class DevicePublic(BaseModel):
    id: UUID
    client_device_id: str
    os: str
    os_version: str
    model: str
    app_version: str
    push_provider: str | None = None
    has_notification_token: bool = False


class SessionPublic(BaseModel):
    id: UUID
    user_id: UUID
    refresh_token_hash: str
    device: DevicePublic
    created_at: datetime
    expires_at: datetime
    last_active: datetime
    revoked_at: datetime | None
    is_revoked: bool

    @classmethod
    def from_row(cls, row: UserSession) -> SessionPublic:
        d = row.user_device
        device = DevicePublic(
            id=d.id,
            client_device_id=d.client_device_id,
            os=d.os,
            os_version=d.os_version,
            model=d.model,
            app_version=d.app_version,
            push_provider=d.push_provider,
            has_notification_token=d.push_token is not None,
        )
        return cls(
            id=row.id,
            user_id=row.user_id,
            refresh_token_hash=row.refresh_token_hash,
            device=device,
            created_at=row.created_at,
            expires_at=row.expires_at,
            last_active=row.last_active_at,
            revoked_at=row.revoked_at,
            is_revoked=row.revoked_at is not None,
        )


class LogoutResponse(BaseModel):
    message: str


class RevokeTokenResponse(BaseModel):
    message: str


class AuthErrorDetails(ErrorDetails):
    type: ErrorType = Field(
        default=ErrorType.SNACKBAR,
        description="Type of error to display",
    )
    attempts_left: int | None = Field(
        default=None,
        description="Remaining number of attempts before temporary block"
    )

    blocked_until: str | None = Field(
        default=None,
        description="Time until the user is blocked",
    )

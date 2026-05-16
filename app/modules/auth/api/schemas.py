from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.application.dto import DeviceDto, SessionDto
from app.modules.auth.domain.entities import DeviceInfo, DeviceNotifications


class DeviceInfoRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., max_length=64)
    os_version: str = Field(..., max_length=64)
    model: str = Field(..., max_length=128)
    app_version: str = Field(..., max_length=64)
    push_provider: str | None = Field(None, max_length=32)
    push_token: str | None = Field(None, max_length=4096)

    def to_domain(self) -> DeviceInfo:
        return DeviceInfo(
            device_id=self.device_id,
            os=self.os,
            os_version=self.os_version,
            model=self.model,
            app_version=self.app_version,
            push_provider=self.push_provider,
            push_token=self.push_token,
        )


class LoginRequest(BaseModel):
    email: EmailStr
    device: DeviceInfoRequest


class LoginResponse(BaseModel):
    message: str
    login_request_id: str
    otp_expires_in: int


class VerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    login_request_id: str = Field(..., min_length=1, max_length=64)


class VerifyResponse(BaseModel):
    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str


class DeviceNotificationsRequest(BaseModel):
    push_provider: str | None = Field(None, max_length=32)
    push_token: str | None = Field(None, max_length=4096)

    def to_domain(self) -> DeviceNotifications:
        return DeviceNotifications(push_provider=self.push_provider, push_token=self.push_token)


class DeviceNotificationsResponse(BaseModel):
    pass


class DeviceResponse(BaseModel):
    id: UUID
    client_device_id: str
    os: str
    os_version: str
    model: str
    app_version: str
    push_provider: str | None = None
    has_notification_token: bool = False

    @classmethod
    def from_dto(cls, dto: DeviceDto) -> "DeviceResponse":
        return cls(
            id=dto.id,
            client_device_id=dto.client_device_id,
            os=dto.os,
            os_version=dto.os_version,
            model=dto.model,
            app_version=dto.app_version,
            push_provider=dto.push_provider,
            has_notification_token=dto.has_notification_token,
        )


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    refresh_token_hash: str
    device: DeviceResponse
    created_at: datetime
    expires_at: datetime
    last_active: datetime
    revoked_at: datetime | None
    is_revoked: bool

    @classmethod
    def from_dto(cls, dto: SessionDto) -> "SessionResponse":
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            refresh_token_hash=dto.refresh_token_hash,
            device=DeviceResponse.from_dto(dto.device),
            created_at=dto.created_at,
            expires_at=dto.expires_at,
            last_active=dto.last_active,
            revoked_at=dto.revoked_at,
            is_revoked=dto.is_revoked,
        )


class LogoutResponse(BaseModel):
    message: str


class RevokeTokenResponse(BaseModel):
    message: str

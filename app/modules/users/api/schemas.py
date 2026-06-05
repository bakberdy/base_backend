from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.common.pagination.schemas import BaseListRequest
from app.modules.users.application.dto import UserDto
from app.modules.users.application.dto import UserPreferencesDto, UserProfileDto
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme

_PHONE_NUMBER_PATTERN = r"^\+[1-9]\d{7,14}$"
_DIAL_CODE_PATTERN = r"^\+[1-9]\d{0,3}$"
_COUNTRY_CODE_PATTERN = r"^[A-Z]{2}$"
_LOCAL_PHONE_NUMBER_PATTERN = r"^\d{10}$"


class UserListRequest(BaseListRequest):
    status: UserStatus | None = None
    search: str | None = Field(None, min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime
    is_user_data_uploaded: bool

    @classmethod
    def from_dto(cls, dto: UserDto) -> "UserResponse":
        return cls(
            id=dto.id,
            email=dto.email,
            role=dto.role,
            status=dto.status,
            is_verified=dto.is_verified,
            created_at=dto.created_at,
            is_user_data_uploaded=dto.is_user_data_uploaded,
        )


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class UpdateUserStatusRequest(BaseModel):
    status: UserStatus


class PhoneNumberRequest(BaseModel):
    country_code: str | None = Field(None, pattern=_COUNTRY_CODE_PATTERN)
    dial_code: str = Field(..., pattern=_DIAL_CODE_PATTERN)
    number: str = Field(..., pattern=_LOCAL_PHONE_NUMBER_PATTERN)


class CreateUserProfileRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    phone_number: PhoneNumberRequest | None = None


class UpdateUserProfileRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone_number: PhoneNumberRequest | None = None

    @model_validator(mode="after")
    def ensure_any_field(self) -> "UpdateUserProfileRequest":
        if not self.model_fields_set:
            raise ValueError("at_least_one_field_required")
        return self


class UserProfileResponse(BaseModel):
    user_id: UUID
    full_name: str
    phone_number: PhoneNumberRequest | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_dto(cls, dto: UserProfileDto) -> "UserProfileResponse":
        return cls(
            user_id=dto.user_id,
            full_name=dto.full_name,
            phone_number=(
                None
                if dto.phone_number is None
                else PhoneNumberRequest(
                    country_code=dto.phone_number.country_code,
                    dial_code=dto.phone_number.dial_code,
                    number=dto.phone_number.number,
                )
            ),
            avatar_url=dto.avatar_url,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            completed_at=dto.completed_at,
        )


class CreateUserPreferencesRequest(BaseModel):
    language: UserLanguage = UserLanguage.EN
    theme: UserTheme = UserTheme.SYSTEM
    push_notifications_enabled: bool = True
    email_notifications_enabled: bool = True
    marketing_notifications_enabled: bool = False


class UpdateUserPreferencesRequest(BaseModel):
    language: UserLanguage | None = None
    theme: UserTheme | None = None
    push_notifications_enabled: bool | None = None
    email_notifications_enabled: bool | None = None
    marketing_notifications_enabled: bool | None = None

    @model_validator(mode="after")
    def ensure_any_field(self) -> "UpdateUserPreferencesRequest":
        if not self.model_fields_set:
            raise ValueError("at_least_one_field_required")
        return self


class UserPreferencesResponse(BaseModel):
    user_id: UUID
    language: UserLanguage
    theme: UserTheme
    push_notifications_enabled: bool
    email_notifications_enabled: bool
    marketing_notifications_enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dto(cls, dto: UserPreferencesDto) -> "UserPreferencesResponse":
        return cls(
            user_id=dto.user_id,
            language=dto.language,
            theme=dto.theme,
            push_notifications_enabled=dto.push_notifications_enabled,
            email_notifications_enabled=dto.email_notifications_enabled,
            marketing_notifications_enabled=dto.marketing_notifications_enabled,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
        )

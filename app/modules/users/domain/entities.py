from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime
    is_user_data_uploaded: bool = False


@dataclass(slots=True)
class PhoneNumber:
    country_code: str | None
    dial_code: str
    number: str


@dataclass(slots=True)
class UserProfile:
    user_id: UUID
    full_name: str
    phone_number: PhoneNumber | None
    avatar_url: str | None
    avatar_object_key: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class UserPreferences:
    user_id: UUID
    language: UserLanguage
    theme: UserTheme
    push_notifications_enabled: bool
    email_notifications_enabled: bool
    marketing_notifications_enabled: bool
    created_at: datetime
    updated_at: datetime

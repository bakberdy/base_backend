from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.pagination.schemas import PaginationMeta
from app.modules.users.domain.entities import User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


@dataclass(slots=True)
class UserDto:
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime
    is_user_data_uploaded: bool

    @classmethod
    def from_entity(cls, user: User) -> "UserDto":
        return cls(
            id=user.id,
            email=user.email,
            role=user.role,
            status=user.status,
            is_verified=user.is_verified,
            created_at=user.created_at,
            is_user_data_uploaded=user.is_user_data_uploaded,
        )


@dataclass(slots=True)
class UsersPageDto:
    items: list[UserDto]
    pagination: PaginationMeta


@dataclass(slots=True)
class UserProfileDto:
    user_id: UUID
    full_name: str
    phone_number: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_entity(cls, profile: UserProfile) -> "UserProfileDto":
        return cls(
            user_id=profile.user_id,
            full_name=profile.full_name,
            phone_number=profile.phone_number,
            avatar_url=profile.avatar_url,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            completed_at=profile.completed_at,
        )


@dataclass(slots=True)
class UserPreferencesDto:
    user_id: UUID
    language: UserLanguage
    theme: UserTheme
    push_notifications_enabled: bool
    email_notifications_enabled: bool
    marketing_notifications_enabled: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, preferences: UserPreferences) -> "UserPreferencesDto":
        return cls(
            user_id=preferences.user_id,
            language=preferences.language,
            theme=preferences.theme,
            push_notifications_enabled=preferences.push_notifications_enabled,
            email_notifications_enabled=preferences.email_notifications_enabled,
            marketing_notifications_enabled=preferences.marketing_notifications_enabled,
            created_at=preferences.created_at,
            updated_at=preferences.updated_at,
        )

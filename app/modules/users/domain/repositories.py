from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.pagination.schemas import SortingMethod
from app.modules.users.domain.entities import User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme


class UserRepository(Protocol):
    async def get_by_email(self, email: str) -> User | None: ...

    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_or_create(self, email: str, now: datetime) -> User: ...

    async def set_verified(self, user_id: UUID, value: bool) -> None: ...

    async def count_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> int: ...

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[User]: ...

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None: ...

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None: ...

    async def get_profile(self, user_id: UUID) -> UserProfile | None: ...

    async def create_profile(
        self,
        *,
        user_id: UUID,
        full_name: str,
        phone_number: str | None,
        now: datetime,
    ) -> UserProfile: ...

    async def update_profile(
        self,
        *,
        user_id: UUID,
        full_name: str | None,
        phone_number: str | None,
        now: datetime,
    ) -> UserProfile | None: ...

    async def update_avatar(
        self,
        *,
        user_id: UUID,
        avatar_url: str,
        avatar_object_key: str,
        now: datetime,
    ) -> UserProfile | None: ...

    async def clear_avatar(self, *, user_id: UUID, now: datetime) -> UserProfile | None: ...

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None: ...

    async def create_preferences(
        self,
        *,
        user_id: UUID,
        language: UserLanguage,
        theme: UserTheme,
        push_notifications_enabled: bool,
        email_notifications_enabled: bool,
        marketing_notifications_enabled: bool,
        now: datetime,
    ) -> UserPreferences: ...

    async def update_preferences(
        self,
        *,
        user_id: UUID,
        language: UserLanguage | None,
        theme: UserTheme | None,
        push_notifications_enabled: bool | None,
        email_notifications_enabled: bool | None,
        marketing_notifications_enabled: bool | None,
        now: datetime,
    ) -> UserPreferences | None: ...

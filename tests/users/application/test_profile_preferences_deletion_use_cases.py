import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest

from app.common.pagination.schemas import SortingMethod
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.users.application.use_cases.approve_user_deletion_request import (
    ApproveUserDeletionRequestUseCase,
)
from app.modules.users.application.use_cases.create_user_preferences import CreateUserPreferencesUseCase
from app.modules.users.application.use_cases.create_user_profile import CreateUserProfileUseCase
from app.modules.users.application.use_cases.request_account_deletion import RequestAccountDeletionUseCase
from app.modules.users.application.use_cases.remove_user_avatar import RemoveUserAvatarUseCase
from app.modules.users.application.use_cases.update_user_avatar import UpdateUserAvatarUseCase
from app.modules.users.application.use_cases.update_user_preferences import UpdateUserPreferencesUseCase
from app.modules.users.domain.entities import PhoneNumber, User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme
from app.modules.users.domain.exceptions import (
    InvalidAvatarUploadError,
    InvalidUserStatusTransitionError,
    UserProfileAlreadyExistsError,
)


class UnitOfWorkSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class AuthRepositorySpy:
    def __init__(self) -> None:
        self.revoked_users: list[UUID] = []

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        self.revoked_users.append(user_id)


class AvatarStorageSpy:
    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    async def save_avatar(
        self,
        *,
        user_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[str, str]:
        return (f"/uploads/avatars/{user_id}/{filename}", f"{user_id}/{filename}")

    async def delete_avatar(self, *, object_key: str) -> None:
        self.deleted_keys.append(object_key)


class UserRepositorySpy:
    def __init__(self, users: dict[UUID, User]) -> None:
        self.users = users
        self.profiles: dict[UUID, UserProfile] = {}
        self.preferences: dict[UUID, UserPreferences] = {}

    async def get_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_or_create(self, email: str, now: datetime) -> User:
        raise NotImplementedError

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        raise NotImplementedError

    async def count_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> int:
        raise NotImplementedError

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
    ) -> list[User]:
        raise NotImplementedError

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None:
        raise NotImplementedError

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        user = self.users.get(user_id)
        if user is None:
            return None
        updated = User(
            id=user.id,
            email=user.email,
            role=user.role,
            status=status,
            is_verified=user.is_verified,
            created_at=user.created_at,
            is_user_data_uploaded=user.is_user_data_uploaded,
        )
        self.users[user_id] = updated
        return updated

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        return self.profiles.get(user_id)

    async def create_profile(
        self,
        *,
        user_id: UUID,
        full_name: str,
        phone_number: PhoneNumber | None,
        now: datetime,
    ) -> UserProfile:
        profile = UserProfile(
            user_id=user_id,
            full_name=full_name,
            phone_number=phone_number,
            avatar_url=None,
            avatar_object_key=None,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        self.profiles[user_id] = profile
        return profile

    async def update_profile(
        self,
        *,
        user_id: UUID,
        full_name: str | None,
        phone_number: PhoneNumber | None,
        now: datetime,
    ) -> UserProfile | None:
        raise NotImplementedError

    async def update_avatar(
        self,
        *,
        user_id: UUID,
        avatar_url: str,
        avatar_object_key: str,
        now: datetime,
    ) -> UserProfile | None:
        profile = self.profiles.get(user_id)
        if profile is None:
            return None
        updated = UserProfile(
            user_id=profile.user_id,
            full_name=profile.full_name,
            phone_number=profile.phone_number,
            avatar_url=avatar_url,
            avatar_object_key=avatar_object_key,
            created_at=profile.created_at,
            updated_at=now,
            completed_at=profile.completed_at,
        )
        self.profiles[user_id] = updated
        return updated

    async def clear_avatar(self, *, user_id: UUID, now: datetime) -> UserProfile | None:
        profile = self.profiles.get(user_id)
        if profile is None:
            return None
        updated = UserProfile(
            user_id=profile.user_id,
            full_name=profile.full_name,
            phone_number=profile.phone_number,
            avatar_url=None,
            avatar_object_key=None,
            created_at=profile.created_at,
            updated_at=now,
            completed_at=profile.completed_at,
        )
        self.profiles[user_id] = updated
        return updated

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)

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
    ) -> UserPreferences:
        preferences = UserPreferences(
            user_id=user_id,
            language=language,
            theme=theme,
            push_notifications_enabled=push_notifications_enabled,
            email_notifications_enabled=email_notifications_enabled,
            marketing_notifications_enabled=marketing_notifications_enabled,
            created_at=now,
            updated_at=now,
        )
        self.preferences[user_id] = preferences
        return preferences

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
    ) -> UserPreferences | None:
        preferences = self.preferences.get(user_id)
        if preferences is None:
            return None
        updated = UserPreferences(
            user_id=user_id,
            language=language or preferences.language,
            theme=theme or preferences.theme,
            push_notifications_enabled=(
                push_notifications_enabled
                if push_notifications_enabled is not None
                else preferences.push_notifications_enabled
            ),
            email_notifications_enabled=(
                email_notifications_enabled
                if email_notifications_enabled is not None
                else preferences.email_notifications_enabled
            ),
            marketing_notifications_enabled=(
                marketing_notifications_enabled
                if marketing_notifications_enabled is not None
                else preferences.marketing_notifications_enabled
            ),
            created_at=preferences.created_at,
            updated_at=now,
        )
        self.preferences[user_id] = updated
        return updated


def make_user(*, role: UserRole = UserRole.USER, status: UserStatus = UserStatus.ACTIVE) -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        role=role,
        status=status,
        is_verified=True,
        created_at=datetime.now(UTC),
    )


def test_create_profile_marks_initial_user_data_uploaded_and_rejects_duplicate() -> None:
    async def scenario() -> None:
        user = make_user()
        repo = UserRepositorySpy({user.id: user})
        unit_of_work = UnitOfWorkSpy()
        use_case = CreateUserProfileUseCase(repo, unit_of_work)

        profile = await use_case.execute(
            user.id,
            full_name="John Smith",
            phone_number=PhoneNumber(country_code="KZ", dial_code="+7", number="7001234567"),
        )

        assert profile.full_name == "John Smith"
        assert profile.completed_at is not None
        assert unit_of_work.commits == 1
        with pytest.raises(UserProfileAlreadyExistsError):
            await use_case.execute(
                user.id,
                full_name="John Smith",
                phone_number=None,
            )

    asyncio.run(scenario())


def test_preferences_create_and_partial_update() -> None:
    async def scenario() -> None:
        user = make_user()
        repo = UserRepositorySpy({user.id: user})
        unit_of_work = UnitOfWorkSpy()
        create_use_case = CreateUserPreferencesUseCase(repo, unit_of_work)
        update_use_case = UpdateUserPreferencesUseCase(repo, unit_of_work)

        created = await create_use_case.execute(
            user.id,
            language=UserLanguage.EN,
            theme=UserTheme.SYSTEM,
            push_notifications_enabled=True,
            email_notifications_enabled=True,
            marketing_notifications_enabled=False,
        )
        updated = await update_use_case.execute(
            user.id,
            language=UserLanguage.RU,
            push_notifications_enabled=False,
        )

        assert created.theme == UserTheme.SYSTEM
        assert updated.language == UserLanguage.RU
        assert updated.theme == UserTheme.SYSTEM
        assert updated.push_notifications_enabled is False

    asyncio.run(scenario())


def test_avatar_upload_validates_content_type_and_updates_profile() -> None:
    async def scenario() -> None:
        user = make_user()
        repo = UserRepositorySpy({user.id: user})
        await repo.create_profile(user_id=user.id, full_name="John Smith", phone_number=None, now=datetime.now(UTC))
        use_case = UpdateUserAvatarUseCase(repo, AvatarStorageSpy(), UnitOfWorkSpy())

        with pytest.raises(InvalidAvatarUploadError):
            await use_case.execute(user.id, filename="avatar.txt", content_type="text/plain", content=b"content")

        profile = await use_case.execute(
            user.id,
            filename="avatar.png",
            content_type="image/png",
            content=b"content",
        )

        assert profile.avatar_url == f"/uploads/avatars/{user.id}/avatar.png"

    asyncio.run(scenario())


def test_remove_avatar_deletes_storage_object_and_clears_profile_fields() -> None:
    async def scenario() -> None:
        user = make_user()
        repo = UserRepositorySpy({user.id: user})
        await repo.create_profile(user_id=user.id, full_name="John Smith", phone_number=None, now=datetime.now(UTC))
        profile_with_avatar = await repo.update_avatar(
            user_id=user.id,
            avatar_url="/uploads/avatars/avatar.png",
            avatar_object_key=f"{user.id}/avatar.png",
            now=datetime.now(UTC),
        )
        assert profile_with_avatar is not None
        storage = AvatarStorageSpy()
        use_case = RemoveUserAvatarUseCase(repo, storage, UnitOfWorkSpy())

        profile = await use_case.execute(user.id)

        assert storage.deleted_keys == [f"{user.id}/avatar.png"]
        assert profile.avatar_url is None

    asyncio.run(scenario())


def test_account_deletion_request_and_admin_approval_soft_delete_user() -> None:
    async def scenario() -> None:
        admin = make_user(role=UserRole.ADMIN)
        user = make_user()
        repo = UserRepositorySpy({admin.id: admin, user.id: user})
        auth_repo = AuthRepositorySpy()

        requested = await RequestAccountDeletionUseCase(repo, UnitOfWorkSpy()).execute(user.id)
        approved = await ApproveUserDeletionRequestUseCase(repo, cast(AuthRepository, auth_repo), UnitOfWorkSpy()).execute(
            admin.id,
            user.id,
        )

        assert requested.status == UserStatus.DELETION_REQUESTED
        assert approved.status == UserStatus.DELETED
        assert auth_repo.revoked_users == [user.id]

    asyncio.run(scenario())


def test_admin_approval_requires_deletion_requested_status() -> None:
    async def scenario() -> None:
        admin = make_user(role=UserRole.ADMIN)
        user = make_user()
        repo = UserRepositorySpy({admin.id: admin, user.id: user})

        with pytest.raises(InvalidUserStatusTransitionError):
            await ApproveUserDeletionRequestUseCase(
                repo,
                cast(AuthRepository, AuthRepositorySpy()),
                UnitOfWorkSpy(),
            ).execute(
                admin.id,
                user.id,
            )

    asyncio.run(scenario())

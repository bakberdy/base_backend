import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.common.pagination.schemas import SortingMethod
from app.modules.users.application.dto import UserDto
from app.modules.users.application.use_cases.change_user_role import ChangeUserRoleUseCase
from app.modules.users.domain.entities import User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme
from app.modules.users.domain.exceptions import ForbiddenUserActionError


class UnitOfWorkSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class UserRepositorySpy:
    def __init__(self, users: dict[UUID, User]) -> None:
        self.users = users
        self.updated_roles: list[tuple[UUID, UserRole]] = []

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        raise NotImplementedError

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
        self.updated_roles.append((user_id, role))
        user = self.users.get(user_id)
        if user is None:
            return None
        return User(
            id=user.id,
            email=user.email,
            role=role,
            status=user.status,
            is_verified=user.is_verified,
            created_at=user.created_at,
        )

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        raise NotImplementedError

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        raise NotImplementedError

    async def create_profile(
        self,
        *,
        user_id: UUID,
        full_name: str,
        phone_number: str | None,
        now: datetime,
    ) -> UserProfile:
        raise NotImplementedError

    async def update_profile(
        self,
        *,
        user_id: UUID,
        full_name: str | None,
        phone_number: str | None,
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
        raise NotImplementedError

    async def clear_avatar(self, *, user_id: UUID, now: datetime) -> UserProfile | None:
        raise NotImplementedError

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError


def make_user(*, role: UserRole, status: UserStatus = UserStatus.ACTIVE) -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        role=role,
        status=status,
        is_verified=True,
        created_at=datetime.now(UTC),
    )


def execute(use_case: ChangeUserRoleUseCase, actor_id: UUID, target_id: UUID, role: UserRole) -> UserDto:
    return asyncio.run(use_case.execute(actor_id, target_id, role))


def test_super_admin_can_change_user_role() -> None:
    actor = make_user(role=UserRole.SUPER_ADMIN)
    target = make_user(role=UserRole.USER)
    repository = UserRepositorySpy({actor.id: actor, target.id: target})
    unit_of_work = UnitOfWorkSpy()
    use_case = ChangeUserRoleUseCase(repository, unit_of_work)

    result = execute(use_case, actor.id, target.id, UserRole.ADMIN)

    assert result.id == target.id
    assert result.role == UserRole.ADMIN
    assert repository.updated_roles == [(target.id, UserRole.ADMIN)]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


def test_admin_cannot_escalate_roles() -> None:
    actor = make_user(role=UserRole.ADMIN)
    target = make_user(role=UserRole.USER)
    repository = UserRepositorySpy({actor.id: actor, target.id: target})
    unit_of_work = UnitOfWorkSpy()
    use_case = ChangeUserRoleUseCase(repository, unit_of_work)

    try:
        execute(use_case, actor.id, target.id, UserRole.ADMIN)
    except ForbiddenUserActionError:
        pass
    else:
        raise AssertionError("admin must not be able to change roles")

    assert repository.updated_roles == []
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 0

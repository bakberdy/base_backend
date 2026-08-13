import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.common.pagination.schemas import SortingMethod
from app.modules.users.api.schemas import UserListRequest
from app.modules.users.application.use_cases.get_users import GetUsersUseCase
from app.modules.users.domain.entities import PhoneNumber, User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme


class UserRepositorySpy:
    def __init__(self, actor: User, rows: list[User] | None = None) -> None:
        self.actor = actor
        self.rows = rows or []
        self.count_calls: list[dict[str, object]] = []
        self.list_calls: list[dict[str, object]] = []

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.actor if user_id == self.actor.id else None

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
        is_verified: bool | None = None,
        is_profile_completed: bool | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        search: str | None = None,
    ) -> int:
        self.count_calls.append(locals() | {"self": None})
        return len(self.rows)

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        is_verified: bool | None = None,
        is_profile_completed: bool | None = None,
        created_at_from: datetime | None = None,
        created_at_to: datetime | None = None,
        search: str | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[User]:
        self.list_calls.append(locals() | {"self": None})
        return self.rows

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None:
        raise NotImplementedError

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        raise NotImplementedError

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        raise NotImplementedError

    async def create_profile(
        self,
        *,
        user_id: UUID,
        full_name: str,
        phone_number: PhoneNumber | None,
        now: datetime,
    ) -> UserProfile:
        raise NotImplementedError

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


def make_user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        email=f"{uuid4().hex}@example.com",
        role=role,
        status=UserStatus.ACTIVE,
        is_verified=True,
        created_at=datetime.now(UTC),
    )


def test_get_users_forwards_filters_for_super_admin() -> None:
    async def scenario() -> None:
        actor = make_user(UserRole.SUPER_ADMIN)
        row = make_user(UserRole.ADMIN)
        repository = UserRepositorySpy(actor, rows=[row])
        use_case = GetUsersUseCase(repository)
        created_at_from = datetime.now(UTC) - timedelta(days=7)
        created_at_to = datetime.now(UTC)

        result = await use_case.execute(
            actor.role,
            UserListRequest(
                page_number=1,
                limit=20,
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                is_verified=True,
                is_profile_completed=False,
                created_at_from=created_at_from,
                created_at_to=created_at_to,
                search="admin",
                sort_key="email",
                sorting_method=SortingMethod.ASC,
            ),
        )

        assert [item.id for item in result.items] == [row.id]
        assert repository.count_calls == [
            {
                "self": None,
                "role": UserRole.ADMIN,
                "status": UserStatus.ACTIVE,
                "is_verified": True,
                "is_profile_completed": False,
                "created_at_from": created_at_from,
                "created_at_to": created_at_to,
                "search": "admin",
            },
        ]
        assert repository.list_calls[0]["role"] == UserRole.ADMIN
        assert repository.list_calls[0]["is_verified"] is True
        assert repository.list_calls[0]["is_profile_completed"] is False
        assert repository.list_calls[0]["created_at_from"] == created_at_from
        assert repository.list_calls[0]["created_at_to"] == created_at_to
        assert repository.list_calls[0]["search"] == "admin"
        assert repository.list_calls[0]["sort_key"] == "email"
        assert repository.list_calls[0]["sorting_method"] == SortingMethod.ASC

    asyncio.run(scenario())


def test_get_users_admin_role_filter_cannot_escape_user_scope() -> None:
    async def scenario() -> None:
        actor = make_user(UserRole.ADMIN)
        repository = UserRepositorySpy(actor, rows=[make_user(UserRole.ADMIN)])
        use_case = GetUsersUseCase(repository)

        result = await use_case.execute(
            actor.role,
            UserListRequest(
                page_number=1,
                limit=20,
                role=UserRole.ADMIN,
                sort_key="created_at",
                search=None,
            ),
        )

        assert result.items == []
        assert result.pagination.total_items == 0
        assert repository.count_calls == []
        assert repository.list_calls == []

    asyncio.run(scenario())

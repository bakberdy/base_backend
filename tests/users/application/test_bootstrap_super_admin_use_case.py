import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.users.application.use_cases.bootstrap_super_admin import (
    BootstrapSuperAdminUseCase,
)
from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus
from tests.access_state import AccessStateStoreSpy


class UserRepositoryFake:
    def __init__(self, user: User) -> None:
        self.user = user
        self.requested_emails: list[str] = []
        self.updated_roles: list[UserRole] = []

    async def get_or_create(self, email: str, _now: datetime) -> User:
        self.requested_emails.append(email)
        return self.user

    async def update_role(self, _user_id, role: UserRole) -> User:
        self.updated_roles.append(role)
        self.user = replace(
            self.user,
            role=role,
            authorization_version=self.user.authorization_version + 1,
        )
        return self.user


class UnitOfWorkSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def make_user(role: UserRole) -> User:
    return User(
        id=uuid4(),
        email="bootstrap@example.com",
        role=role,
        status=UserStatus.ACTIVE,
        is_verified=False,
        created_at=datetime.now(UTC),
    )


def test_bootstrap_promotes_user_and_normalizes_email() -> None:
    repository = UserRepositoryFake(make_user(UserRole.USER))
    unit_of_work = UnitOfWorkSpy()

    result = asyncio.run(
        BootstrapSuperAdminUseCase(repository, AccessStateStoreSpy(), unit_of_work).execute(
            "  Initial.Admin@Example.COM ",
        )
    )

    assert result.role == UserRole.SUPER_ADMIN
    assert repository.requested_emails == ["initial.admin@example.com"]
    assert repository.updated_roles == [UserRole.SUPER_ADMIN]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


def test_bootstrap_is_idempotent_for_existing_super_admin() -> None:
    repository = UserRepositoryFake(make_user(UserRole.SUPER_ADMIN))
    unit_of_work = UnitOfWorkSpy()

    result = asyncio.run(
        BootstrapSuperAdminUseCase(repository, AccessStateStoreSpy(), unit_of_work).execute(
            "initial.admin@example.com",
        )
    )

    assert result.role == UserRole.SUPER_ADMIN
    assert repository.updated_roles == []
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0

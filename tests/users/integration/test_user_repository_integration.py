import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.pagination.exceptions import InvalidSortKeyError
from app.common.pagination.schemas import SortingMethod
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.infrastructure.sqlalchemy_models import UserModel
from app.modules.users.infrastructure.sqlalchemy_repositories import SqlAlchemyUserRepository


pytestmark = pytest.mark.integration


def test_user_repository_filters_paginates_and_sorts_with_real_database(
    integration_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        now = datetime.now(UTC)
        records = [
            UserModel(
                id=uuid4(),
                email="old-admin@example.com",
                role=UserRole.ADMIN.value,
                status=UserStatus.ACTIVE.value,
                is_verified=True,
                created_at=now - timedelta(days=3),
            ),
            UserModel(
                id=uuid4(),
                email="new-user@example.com",
                role=UserRole.USER.value,
                status=UserStatus.ACTIVE.value,
                is_verified=True,
                created_at=now,
            ),
            UserModel(
                id=uuid4(),
                email="middle-admin@example.com",
                role=UserRole.ADMIN.value,
                status=UserStatus.BLOCKED.value,
                is_verified=False,
                created_at=now - timedelta(days=1),
            ),
        ]

        async with integration_session_maker() as session:
            session.add_all(records)
            await session.commit()

        async with integration_session_maker() as session:
            repository = SqlAlchemyUserRepository(session)

            first_page = await repository.list_users(offset=0, limit=2)
            admin_page = await repository.list_users(offset=0, limit=10, role=UserRole.ADMIN)
            email_sorted_page = await repository.list_users(
                offset=0,
                limit=10,
                sort_key="email",
                sorting_method=SortingMethod.ASC,
            )
            admin_count = await repository.count_users(role=UserRole.ADMIN)

        assert [user.email for user in first_page] == [
            "new-user@example.com",
            "middle-admin@example.com",
        ]
        assert [user.email for user in admin_page] == [
            "middle-admin@example.com",
            "old-admin@example.com",
        ]
        assert [user.email for user in email_sorted_page] == [
            "middle-admin@example.com",
            "new-user@example.com",
            "old-admin@example.com",
        ]
        assert admin_count == 2

    asyncio.run(scenario())


def test_user_repository_rejects_unknown_sort_key(
    integration_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        async with integration_session_maker() as session:
            repository = SqlAlchemyUserRepository(session)

            with pytest.raises(InvalidSortKeyError):
                await repository.list_users(offset=0, limit=10, sort_key="not_a_db_column")

    asyncio.run(scenario())


def test_user_repository_persistence_respects_transaction_rollback(
    integration_session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async def scenario() -> None:
        email = f"rollback-{uuid4().hex}@example.com"

        async with integration_session_maker() as session:
            repository = SqlAlchemyUserRepository(session)
            created = await repository.get_or_create(email, datetime.now(UTC))
            assert created.email == email
            await session.rollback()

        async with integration_session_maker() as session:
            repository = SqlAlchemyUserRepository(session)
            assert await repository.get_by_email(email) is None

    asyncio.run(scenario())

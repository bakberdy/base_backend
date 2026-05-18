from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination.schemas import SortingMethod
from app.common.pagination.sqlalchemy import apply_sorting, model_sort_columns
from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.sqlalchemy_models import UserModel


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        role=UserRole(model.role),
        status=UserStatus(model.status),
        is_verified=model.is_verified,
        created_at=model.created_at,
    )


_USER_SORT_COLUMNS = model_sort_columns(UserModel)


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

    async def get_or_create(self, email: str, now: datetime) -> User:
        existing = await self.get_by_email(email)
        if existing is not None:
            return existing
        row = UserModel(
            id=uuid4(),
            email=email,
            role=UserRole.USER.value,
            status=UserStatus.ACTIVE.value,
            is_verified=False,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        if row is not None:
            row.is_verified = value

    async def count_users(self, *, role: UserRole | None = None) -> int:
        conditions = []
        if role is not None:
            conditions.append(UserModel.role == role.value)
        result = await self._session.execute(select(func.count()).select_from(UserModel).where(*conditions))
        return int(result.scalar_one() or 0)

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: UserRole | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[User]:
        conditions = []
        if role is not None:
            conditions.append(UserModel.role == role.value)
        stmt = apply_sorting(
            select(UserModel).where(*conditions),
            sort_key=sort_key,
            sorting_method=sorting_method,
            sort_columns=_USER_SORT_COLUMNS,
        )
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [_to_entity(row) for row in result.scalars().all()]

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None:
        stmt = update(UserModel).where(UserModel.id == user_id).values(role=role.value).returning(UserModel)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        stmt = update(UserModel).where(UserModel.id == user_id).values(status=status.value).returning(UserModel)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

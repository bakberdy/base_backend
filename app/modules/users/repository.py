from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.schemas import UserRole, UserStatus


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_or_create(self, email: str, now: datetime) -> User:
        existing = await self.get_by_email(email)
        if existing is not None:
            return existing
        user = User(
            id=uuid4(),
            email=email,
            role=UserRole.USER.value,
            status=UserStatus.ACTIVE.value,
            is_verified=False,
            created_at=now,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            return
        user.is_verified = value

    async def count_users(self, *, role: UserRole | None = None) -> int:
        conditions = []
        if role is not None:
            conditions.append(User.role == role.value)
        stmt = select(func.count()).select_from(User).where(*conditions)
        res = await self._session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: UserRole | None = None,
    ) -> list[User]:
        conditions = []
        if role is not None:
            conditions.append(User.role == role.value)
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(role=role.value)
            .returning(User)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(status=status.value)
            .returning(User)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

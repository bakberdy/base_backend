from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


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
        user = User(id=uuid4(), email=email, is_verified=False, created_at=now)
        self._session.add(user)
        await self._session.flush()
        return user

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        user = await self.get_by_id(user_id)
        if user is None:
            return
        user.is_verified = value

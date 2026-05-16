from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.pagination.schemas import PaginationMeta
from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus


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

    @classmethod
    def from_entity(cls, user: User) -> "UserDto":
        return cls(
            id=user.id,
            email=user.email,
            role=user.role,
            status=user.status,
            is_verified=user.is_verified,
            created_at=user.created_at,
        )


@dataclass(slots=True)
class UsersPageDto:
    items: list[UserDto]
    pagination: PaginationMeta

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.modules.users.application.dto import UserDto
from app.modules.users.domain.enums import UserRole, UserStatus


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: UserDto) -> "UserResponse":
        return cls(
            id=dto.id,
            email=dto.email,
            role=dto.role,
            status=dto.status,
            is_verified=dto.is_verified,
            created_at=dto.created_at,
        )


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class UpdateUserStatusRequest(BaseModel):
    status: UserStatus

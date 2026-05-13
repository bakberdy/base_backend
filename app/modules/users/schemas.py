from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRoleBody(BaseModel):
    role: UserRole


class UpdateUserStatusBody(BaseModel):
    status: UserStatus

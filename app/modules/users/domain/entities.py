from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.users.domain.enums import UserRole, UserStatus


@dataclass(slots=True)
class User:
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    created_at: datetime

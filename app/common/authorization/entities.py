from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.common.authorization.enums import UserRole, UserStatus


class AuthorizationIdentity(Protocol):
    id: UUID
    email: str
    role: UserRole
    status: UserStatus
    is_verified: bool
    authorization_version: int


@dataclass(frozen=True, slots=True)
class CurrentPrincipal:
    user_id: UUID
    session_id: UUID
    role: UserRole
    authorization_version: int


@dataclass(frozen=True, slots=True)
class CachedAccessState:
    authorization_version: int | None
    session_active: bool | None


class AuthorizationSession(Protocol):
    id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None

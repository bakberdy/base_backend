from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class UserStatus(StrEnum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETION_REQUESTED = "deletion_requested"
    DELETED = "deleted"

from enum import StrEnum

from app.common.authorization.enums import UserRole as UserRole
from app.common.authorization.enums import UserStatus as UserStatus

__all__ = ["UserLanguage", "UserRole", "UserStatus", "UserTheme"]


class UserLanguage(StrEnum):
    EN = "en"
    RU = "ru"
    KK = "kk"


class UserTheme(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"

from app.common.exceptions.base import ApplicationError


class UserNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_NOT_FOUND")


class ForbiddenUserActionError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("FORBIDDEN")


class UserProfileAlreadyExistsError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_PROFILE_ALREADY_EXISTS")


class UserProfileNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_PROFILE_NOT_FOUND")


class UserPreferencesAlreadyExistsError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_PREFERENCES_ALREADY_EXISTS")


class UserPreferencesNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_PREFERENCES_NOT_FOUND")


class InvalidUserStatusTransitionError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("INVALID_USER_STATUS_TRANSITION")


class InvalidAvatarUploadError(ApplicationError):
    def __init__(self, reason: str) -> None:
        super().__init__("INVALID_AVATAR_UPLOAD", {"reason": reason})

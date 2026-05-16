from app.common.exceptions.base import ApplicationError


class UserNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("USER_NOT_FOUND")


class ForbiddenUserActionError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("FORBIDDEN")

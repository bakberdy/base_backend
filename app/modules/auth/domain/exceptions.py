from app.common.exceptions.base import ApplicationError


class InvalidLoginRequestError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("INVALID_LOGIN_REQUEST")


class InvalidCredentialsError(ApplicationError):
    def __init__(self, *, attempts_left: int | None = None) -> None:
        details = {"attempts_left": attempts_left} if attempts_left is not None else {}
        super().__init__("INVALID_CREDENTIALS", details)


class LoginRequestAlreadyUsedError(ApplicationError):
    def __init__(self, *, attempts_left: int | None = None) -> None:
        details = {"attempts_left": attempts_left} if attempts_left is not None else {}
        super().__init__("LOGIN_REQUEST_ALREADY_USED", details)


class OtpExpiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("OTP_EXPIRED")


class TooManyAttemptsError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("TOO_MANY_ATTEMPTS")


class InvalidOtpError(ApplicationError):
    def __init__(self, *, attempts_left: int) -> None:
        super().__init__("INVALID_OTP", {"attempts_left": attempts_left})


class TokenExpiredError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("TOKEN_EXPIRED")


class InvalidTokenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("INVALID_TOKEN")


class InvalidRefreshTokenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("INVALID_REFRESH_TOKEN")


class SessionNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("SESSION_NOT_FOUND")


class ForbiddenSessionError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("FORBIDDEN")


class SessionAlreadyRevokedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("SESSION_ALREADY_REVOKED")


class SessionRevokedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("SESSION_REVOKED")

from typing import Any


class ApplicationError(Exception):
    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        Exception.__init__(self, code)


class ForbiddenError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("FORBIDDEN")


class DependencyUnavailableError(ApplicationError):
    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__("DEPENDENCY_UNAVAILABLE")


class InvalidDependencyStateError(ApplicationError):
    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__("INVALID_DEPENDENCY_STATE")

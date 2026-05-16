from typing import Any


class ApplicationError(Exception):
    def __init__(self, code: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.details = details or {}
        Exception.__init__(self, code)

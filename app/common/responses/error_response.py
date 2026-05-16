from enum import Enum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class ErrorType(Enum):
    SNACKBAR = "snackbar"
    BANNER = "banner"
    INLINE_ERROR = "inline"
    ALERT = "alert"
    FULL_SCREEN = "full_screen"
    SILENT = "silent"


class FieldError(BaseModel):
    field_name: str
    message: str = Field(..., description="Localized display message")


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: ErrorType = Field(..., description="Type of error to display")
    field_errors: list[FieldError] | None = Field(
        default=None,
        description="List of validation errors related to specific request fields",
    )
    status_code: int = Field(..., description="HTTP status code")


class ErrorResponse(BaseModel):
    message: str = Field(..., description="Localized display message")
    code: int = Field(..., description="HTTP status code")
    details: ErrorDetails = Field(
        ...,
        description="Structured error context (must include type)",
    )


def api_http_exception(
    status_code: int,
    message: str,
    *,
    details: ErrorDetails | None = None,
    error_type: ErrorType | None = None,
    field_errors: list[FieldError] | None = None,
) -> HTTPException:
    if details is None:
        resolved = ErrorDetails(
            status_code=status_code,
            type=error_type or ErrorType.SNACKBAR,
            field_errors=field_errors,
        )
    else:
        patch: dict[str, Any] = {"status_code": status_code}
        if error_type is not None:
            patch["type"] = error_type
        if field_errors is not None:
            patch["field_errors"] = field_errors
        resolved = details.model_copy(update=patch)
    body = ErrorResponse(message=message, code=status_code, details=resolved)
    detail = body.model_dump(mode="json")
    detail["message_key"] = message
    return HTTPException(status_code=status_code, detail=detail)

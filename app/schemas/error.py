from enum import Enum
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.i18n import _


class ErrorType(Enum):
    SNACKBAR = "snackbar"
    BANNER = "banner"
    INLINE_ERROR = "inline"
    ALERT = "alert"
    FULL_SCREEN = "full_screen"
    SILENT = "silent"


class FieldError(BaseModel):
    field_name: str
    message: str


class ErrorDetails(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: ErrorType = Field(
        ...,
        description="Type of error to display",
    )
    field_errors: list[FieldError] | None = Field(
        default=None,
        description="List of validation errors related to specific request fields",
    )
    status_code: int = Field(..., description="HTTP status code")


class ErrorResponse(BaseModel):
    message: str
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
        resolved: ErrorDetails = ErrorDetails(
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
    body = ErrorResponse(message=_(message), code=status_code, details=resolved)
    return HTTPException(
        status_code=status_code,
        detail=body.model_dump(mode="json"),
    )

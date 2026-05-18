import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions.base import ApplicationError
from app.common.localization.service import translate
from app.common.responses.error_response import ErrorDetails, ErrorResponse, ErrorType, FieldError

logger = logging.getLogger(__name__)

_VALIDATION_MESSAGE_KEYS = {
    "missing": "field_required",
    "value_error": "invalid_value",
    "string_type": "invalid_string",
    "string_too_short": "string_too_short",
    "string_too_long": "string_too_long",
    "string_pattern_mismatch": "invalid_format",
    "int_parsing": "invalid_integer",
    "int_type": "invalid_integer",
    "bool_parsing": "invalid_boolean",
    "bool_type": "invalid_boolean",
    "uuid_parsing": "invalid_uuid",
    "uuid_type": "invalid_uuid",
    "greater_than_equal": "value_too_small",
    "less_than_equal": "value_too_large",
    "url_parsing": "invalid_url",
}

_APPLICATION_STATUS_CODES = {
    "FORBIDDEN": status.HTTP_403_FORBIDDEN,
    "INVALID_CREDENTIALS": status.HTTP_400_BAD_REQUEST,
    "INVALID_AVATAR_UPLOAD": status.HTTP_400_BAD_REQUEST,
    "INVALID_LOGIN_REQUEST": status.HTTP_400_BAD_REQUEST,
    "INVALID_OTP": status.HTTP_400_BAD_REQUEST,
    "INVALID_REFRESH_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "INVALID_SORT_KEY": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "INVALID_TOKEN": status.HTTP_401_UNAUTHORIZED,
    "INVALID_USER_STATUS_TRANSITION": status.HTTP_400_BAD_REQUEST,
    "LOGIN_REQUEST_ALREADY_USED": status.HTTP_410_GONE,
    "OTP_EXPIRED": status.HTTP_410_GONE,
    "OTP_DELIVERY_FAILED": status.HTTP_503_SERVICE_UNAVAILABLE,
    "SESSION_ALREADY_REVOKED": status.HTTP_410_GONE,
    "SESSION_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "SESSION_REVOKED": status.HTTP_410_GONE,
    "TOKEN_EXPIRED": status.HTTP_401_UNAUTHORIZED,
    "TOO_MANY_ATTEMPTS": status.HTTP_429_TOO_MANY_REQUESTS,
    "USER_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "USER_PREFERENCES_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
    "USER_PREFERENCES_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "USER_PROFILE_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
    "USER_PROFILE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
}


def _message_key(code: str) -> str:
    return code.lower()


def _localized_response(body: ErrorResponse) -> ErrorResponse:
    details = body.details
    if details.field_errors:
        details = details.model_copy(
            update={
                "field_errors": [
                    error.model_copy(update={"message": translate(error.message)})
                    for error in details.field_errors
                ],
            },
        )
    return body.model_copy(update={"message": translate(body.message), "details": details})


def _error_details_from_extra(
    code: int,
    raw_details: Any,
    rest: dict[str, Any],
) -> ErrorDetails:
    if isinstance(raw_details, ErrorDetails):
        return raw_details.model_copy(update={"status_code": code})

    if isinstance(raw_details, dict):
        merged = {**raw_details, "status_code": raw_details.get("status_code", code)}
        if merged.get("type") is None:
            merged["type"] = ErrorType.SNACKBAR.value
        return ErrorDetails.model_validate(merged)

    if raw_details is not None:
        return ErrorDetails.model_validate({
            "status_code": code,
            "type": ErrorType.BANNER.value,
            "payload": raw_details,
        })

    if rest:
        merged = {"status_code": code, "type": ErrorType.SNACKBAR.value, **rest}
        if merged.get("type") is None:
            merged["type"] = ErrorType.SNACKBAR.value
        return ErrorDetails.model_validate(merged)

    return ErrorDetails(status_code=code, type=ErrorType.SNACKBAR)


def _http_exception_payload(exc: StarletteHTTPException) -> ErrorResponse:
    detail: Any = exc.detail
    status_code = exc.status_code

    if isinstance(detail, dict):
        try:
            return _localized_response(ErrorResponse.model_validate(detail))
        except ValidationError:
            message_key = str(detail.get(
                "message_key",
                detail.get("message", detail.get("msg", "request_failed")),
            ))
            code = int(detail["code"]) if detail.get("code") is not None else status_code
            raw_details = detail.get("details")
            rest = {
                key: value
                for key, value in detail.items()
                if key not in ("message", "msg", "code", "details")
            }
            return _localized_response(
                ErrorResponse(
                    message=message_key,
                    details=_error_details_from_extra(code, raw_details, rest),
                    code=code,
                ),
            )

    if isinstance(detail, str):
        return _localized_response(
            ErrorResponse(
                message=detail,
                details=ErrorDetails(status_code=status_code, type=ErrorType.SNACKBAR),
                code=status_code,
            ),
        )

    details = ErrorDetails.model_validate({
        "status_code": status_code,
        "type": ErrorType.SNACKBAR.value,
        "payload": detail,
    })
    return _localized_response(
        ErrorResponse(message="request_failed", details=details, code=status_code),
    )


def _validation_field_errors(raw_errors: Sequence[Any]) -> list[FieldError]:
    out: list[FieldError] = []
    for err_any in raw_errors:
        if not isinstance(err_any, dict):
            continue
        loc = err_any.get("loc") or ()
        parts = [str(part) for part in loc if part != "body"]
        field_name = ".".join(parts) if parts else "request"
        raw_type = err_any.get("type")
        error_type = raw_type if isinstance(raw_type, str) else "value_error"
        out.append(
            FieldError(
                field_name=field_name,
                message=_VALIDATION_MESSAGE_KEYS.get(error_type, "invalid_value"),
            ),
        )
    return out


async def application_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApplicationError)
    status_code = _APPLICATION_STATUS_CODES.get(exc.code, status.HTTP_400_BAD_REQUEST)
    details_payload = {"status_code": status_code, "type": ErrorType.SNACKBAR.value, **exc.details}
    body = _localized_response(
        ErrorResponse(
            message=_message_key(exc.code),
            code=status_code,
            details=ErrorDetails.model_validate(details_payload),
        ),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    body = _http_exception_payload(exc)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


async def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = ErrorDetails(
        status_code=422,
        type=ErrorType.INLINE_ERROR,
        field_errors=_validation_field_errors(exc.errors()),
    )
    body = _localized_response(ErrorResponse(message="validation_failed", code=422, details=details))
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error")
    body = _localized_response(
        ErrorResponse(
            message="service_unavailable_try_later",
            details=ErrorDetails(status_code=500, type=ErrorType.ALERT),
            code=500,
        ),
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationError, application_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

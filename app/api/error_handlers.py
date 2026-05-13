import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import ValidationError

from app.core.i18n import _, N_
from app.schemas.error import ErrorDetails, ErrorResponse, ErrorType, FieldError

logger = logging.getLogger(__name__)

_VALIDATION_MESSAGE_KEYS = {
    "missing": N_("field_required"),
    "value_error": N_("invalid_value"),
    "string_type": N_("invalid_string"),
    "string_too_short": N_("string_too_short"),
    "string_too_long": N_("string_too_long"),
    "string_pattern_mismatch": N_("invalid_format"),
    "int_parsing": N_("invalid_integer"),
    "int_type": N_("invalid_integer"),
    "bool_parsing": N_("invalid_boolean"),
    "bool_type": N_("invalid_boolean"),
    "uuid_parsing": N_("invalid_uuid"),
    "uuid_type": N_("invalid_uuid"),
    "greater_than_equal": N_("value_too_small"),
    "less_than_equal": N_("value_too_large"),
    "url_parsing": N_("invalid_url"),
}


def _localized_response(body: ErrorResponse) -> ErrorResponse:
    details = body.details
    if details.field_errors:
        details = details.model_copy(
            update={
                "field_errors": [
                    error.model_copy(update={"message": _(error.message)})
                    for error in details.field_errors
                ],
            },
        )
    return body.model_copy(update={"message": _(body.message), "details": details})


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
    status = exc.status_code

    if isinstance(detail, dict):
        try:
            return _localized_response(ErrorResponse.model_validate(detail))
        except ValidationError:
            message_key = str(detail.get(
                "message_key", detail.get("message", detail.get("msg", "request_failed"))))
            code = int(detail["code"]) if detail.get(
                "code") is not None else status
            raw_details = detail.get("details")
            rest = {
                k: v
                for k, v in detail.items()
                if k not in ("message", "msg", "code", "details")
            }
            normalized = _error_details_from_extra(code, raw_details, rest)
            return _localized_response(
                ErrorResponse(
                    message=message_key,
                    details=normalized,
                    code=code,
                ),
            )

    if isinstance(detail, str):
        return _localized_response(
            ErrorResponse(
                message=detail,
                details=ErrorDetails(status_code=status, type=ErrorType.SNACKBAR),
                code=status,
            ),
        )

    if isinstance(detail, list):
        details = ErrorDetails.model_validate({
            "status_code": status,
            "type": ErrorType.INLINE_ERROR.value,
            "payload": detail,
        })
        return _localized_response(
            ErrorResponse(
                message="request_failed",
                details=details,
                code=status,
            ),
        )

    details = ErrorDetails.model_validate({
        "status_code": status,
        "type": ErrorType.SNACKBAR.value,
        "payload": detail,
    })
    return _localized_response(
        ErrorResponse(
            message="request_failed",
            details=details,
            code=status,
        ),
    )


def _validation_field_errors(raw_errors: Sequence[Any]) -> list[FieldError]:
    out: list[FieldError] = []
    for err_any in raw_errors:
        if not isinstance(err_any, dict):
            continue
        err: dict[str, Any] = err_any
        loc = err.get("loc") or ()
        parts = [str(p) for p in loc if p != "body"]
        field_name = ".".join(parts) if parts else "request"
        raw_type = err.get("type")
        error_type = raw_type if isinstance(raw_type, str) else "value_error"
        message_key = _VALIDATION_MESSAGE_KEYS.get(error_type, "invalid_value")
        out.append(
            FieldError(
                field_name=field_name,
                message=message_key,
            ),
        )
    return out


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
    body = _localized_response(
        ErrorResponse(
            message="validation_failed",
            code=422,
            details=details,
        ),
    )
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
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError,
                              validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

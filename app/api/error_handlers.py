import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import ValidationError

from app.core.i18n import _
from app.schemas.error import ErrorDetails, ErrorResponse, ErrorType, FieldError

logger = logging.getLogger(__name__)


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
            return ErrorResponse.model_validate(detail)
        except ValidationError:
            message = str(detail.get(
                "message", detail.get("msg", _("request_failed"))))
            code = int(detail["code"]) if detail.get(
                "code") is not None else status
            raw_details = detail.get("details")
            rest = {
                k: v
                for k, v in detail.items()
                if k not in ("message", "msg", "code", "details")
            }
            normalized = _error_details_from_extra(code, raw_details, rest)
            return ErrorResponse(message=_(message), details=normalized, code=code)

    if isinstance(detail, str):
        return ErrorResponse(
            message=_(detail),
            details=ErrorDetails(status_code=status, type=ErrorType.SNACKBAR),
            code=status,
        )

    if isinstance(detail, list):
        details = ErrorDetails.model_validate({
            "status_code": status,
            "type": ErrorType.INLINE_ERROR.value,
            "payload": detail,
        })
        return ErrorResponse(
            message=_("request_failed"),
            details=details,
            code=status,
        )

    details = ErrorDetails.model_validate({
        "status_code": status,
        "type": ErrorType.SNACKBAR.value,
        "payload": detail,
    })
    return ErrorResponse(message=_("request_failed"), details=details, code=status)


def _validation_field_errors(raw_errors: Sequence[Any]) -> list[FieldError]:
    out: list[FieldError] = []
    for err_any in raw_errors:
        if not isinstance(err_any, dict):
            continue
        err: dict[str, Any] = err_any
        loc = err.get("loc") or ()
        parts = [str(p) for p in loc if p != "body"]
        field_name = ".".join(parts) if parts else "request"
        msg = err.get("msg") or "Invalid value"
        out.append(FieldError(field_name=field_name, message=_(str(msg))))
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
    body = ErrorResponse(message=_("validation_failed"),
                         code=422, details=details)
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def unhandled_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error")
    body = ErrorResponse(
        message=_("service_unavailable_try_later"),
        details=ErrorDetails(
            status_code=500, type=ErrorType.ALERT),
        code=500,
    )
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError,
                              validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

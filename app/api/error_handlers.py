import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.error import ErrorDetails, ErrorResponse, ErrorType, FieldError

logger = logging.getLogger(__name__)


def _http_exception_payload(exc: StarletteHTTPException) -> ErrorResponse:
    detail: Any = exc.detail
    status = exc.status_code

    if isinstance(detail, dict):
        try:
            return ErrorResponse.model_validate(detail)
        except ValidationError:
            message = str(detail.get("message", detail.get("msg", "Request failed")))
            raw_details = detail.get("details")
            if raw_details is not None:
                details_payload: Any = raw_details
            else:
                rest = {
                    k: v
                    for k, v in detail.items()
                    if k not in ("message", "msg", "code")
                }
                details_payload = rest if rest else None
            code = int(detail["code"]) if detail.get("code") is not None else status
            return ErrorResponse(message=message, details=details_payload, code=code)

    if isinstance(detail, str):
        return ErrorResponse(message=detail, details=None, code=status)

    if isinstance(detail, list):
        return ErrorResponse(message="Request failed", details=detail, code=status)

    return ErrorResponse(message="Request failed", details=detail, code=status)


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
        out.append(FieldError(field_name=field_name, message=msg))
    return out


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    body = _http_exception_payload(exc)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def validation_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = ErrorDetails(
        status_code=422,
        type=ErrorType.INLINE_ERROR,
        field_errors=_validation_field_errors(exc.errors()),
    )
    body = ErrorResponse(message="Validation failed", code=422, details=details)
    return JSONResponse(status_code=422, content=body.model_dump(mode="json"))


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error")
    settings = get_settings()
    details = None
    if settings.app_env == "development":
        details = {"type": type(exc).__name__, "detail": str(exc)}
    body = ErrorResponse(
        message="Service is unavailable right now, try it later",
        details=details,
        code=500,
    )
    return JSONResponse(status_code=500, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

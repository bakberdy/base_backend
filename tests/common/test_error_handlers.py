import asyncio
import json
from typing import Any

from limits import parse
from redis.exceptions import ConnectionError as RedisConnectionError
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import Limit
from starlette.requests import Request

from app.common.exceptions.handlers import (
    application_exception_handler,
    dependency_exception_handler,
    rate_limit_exception_handler,
)
from app.common.localization.service import reset_locale, set_locale
from app.modules.auth.domain.exceptions import OtpRecipientRejectedError


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/auth/login",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def _rate_limit_exceeded() -> RateLimitExceeded:
    limit = Limit(
        parse("10/minute"),
        lambda: "testclient",
        None,
        False,
        None,
        None,
        None,
        1,
        False,
    )
    return RateLimitExceeded(limit)


def test_rate_limit_error_uses_shared_error_response_shape() -> None:
    response = asyncio.run(rate_limit_exception_handler(_request(), _rate_limit_exceeded()))
    body: dict[str, Any] = json.loads(response.body)

    assert response.status_code == 429
    assert body == {
        "message": "Too many attempts",
        "code": 429,
        "details": {
            "type": "snackbar",
            "field_errors": None,
            "status_code": 429,
        },
    }


def test_rejected_otp_recipient_returns_localized_inline_email_error() -> None:
    locale_token = set_locale("ru")
    try:
        response = asyncio.run(
            application_exception_handler(
                _request(),
                OtpRecipientRejectedError(),
            )
        )
    finally:
        reset_locale(locale_token)
    body: dict[str, Any] = json.loads(response.body)

    assert response.status_code == 422
    assert body == {
        "message": "Не удалось доставить код. Попробуйте указать другую почту",
        "code": 422,
        "details": {
            "type": "inline",
            "field_errors": [
                {
                    "field_name": "email",
                    "message": "Не удалось доставить код. Попробуйте указать другую почту",
                }
            ],
            "status_code": 422,
        },
    }


def test_redis_failure_returns_unified_dependency_unavailable_error() -> None:
    response = asyncio.run(
        dependency_exception_handler(_request(), RedisConnectionError("synthetic failure"))
    )
    body: dict[str, Any] = json.loads(response.body)

    assert response.status_code == 503
    assert body["code"] == 503
    assert body["message"] == "A required service is temporarily unavailable"
    assert body["details"]["type"] == "alert"

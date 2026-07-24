import asyncio
import json
from typing import Any

from limits import parse
from slowapi.errors import RateLimitExceeded
from slowapi.wrappers import Limit
from starlette.requests import Request

from app.common.exceptions.handlers import rate_limit_exception_handler


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

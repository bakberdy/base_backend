from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import register_middlewares


def test_cors_preflight_allows_configured_origin() -> None:
    app = FastAPI()
    register_middlewares(
        app,
        cors_allowed_origins=["http://localhost:3000"],
        cors_allow_credentials=False,
    )

    response = TestClient(app).options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_is_not_enabled_without_configured_origins() -> None:
    app = FastAPI()
    register_middlewares(
        app,
        cors_allowed_origins=[],
        cors_allow_credentials=False,
    )

    response = TestClient(app).options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert "access-control-allow-origin" not in response.headers

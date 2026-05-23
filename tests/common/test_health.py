from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_health_endpoint_returns_status() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == get_settings().health_status

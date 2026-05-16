from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


def _device_payload(device_id: str) -> dict[str, str]:
    return {
        "device_id": device_id,
        "os": "ios",
        "os_version": "17.5",
        "model": "iPhone 15",
        "app_version": "1.0.0",
        "push_provider": "apns",
        "push_token": f"push-{device_id}",
    }


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "device": _device_payload(f"device-{uuid4().hex}")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["message"]
    assert body["otp_expires_in"] > 0
    return str(body["login_request_id"])


def _verify(client: TestClient, email: str, login_request_id: str, code: str) -> dict[str, str]:
    response = client.post(
        "/auth/verify-email",
        json={"email": email, "code": code, "login_request_id": login_request_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    return {"access_token": str(body["access_token"]), "refresh_token": str(body["refresh_token"])}


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def test_auth_flow_rotates_refresh_token_and_revokes_reused_token(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    if integration_settings.dev_otp_code is None:
        pytest.skip("Auth integration flow needs DEV_OTP_CODE in the test environment")

    email = f"integration-{uuid4().hex}@example.com"
    login_request_id = _login(integration_client, email)
    first_pair = _verify(integration_client, email, login_request_id, integration_settings.dev_otp_code)

    current_user_response = integration_client.get(
        "/users/me",
        headers=_auth_headers(first_pair["access_token"]),
    )
    assert current_user_response.status_code == 200
    current_user = current_user_response.json()
    assert current_user["email"] == email
    assert current_user["is_verified"] is True

    refresh_response = integration_client.post(
        "/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    second_pair = refresh_response.json()
    assert second_pair["access_token"] != first_pair["access_token"]
    assert second_pair["refresh_token"] != first_pair["refresh_token"]

    active_sessions_response = integration_client.get(
        "/auth/sessions",
        params={"is_active": True},
        headers=_auth_headers(str(second_pair["access_token"])),
    )
    assert active_sessions_response.status_code == 200
    active_sessions = active_sessions_response.json()
    assert active_sessions["pagination"]["total_items"] == 1
    assert active_sessions["items"][0]["is_revoked"] is False

    reused_refresh_response = integration_client.post(
        "/auth/refresh",
        json={"refresh_token": first_pair["refresh_token"]},
    )
    assert reused_refresh_response.status_code == 401
    reused_refresh_body = reused_refresh_response.json()
    assert reused_refresh_body["code"] == 401
    assert "message_key" not in reused_refresh_body

    revoked_access_response = integration_client.get(
        "/users/me",
        headers=_auth_headers(str(second_pair["access_token"])),
    )
    assert revoked_access_response.status_code == 410
    assert revoked_access_response.json()["code"] == 410


def test_login_validation_error_is_localized_at_api_boundary(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/auth/login",
        headers={"Accept-Language": "ru"},
        json={"email": "not-an-email", "device": _device_payload("invalid-email-device")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Ошибка валидации"
    assert body["code"] == 422
    assert "message_key" not in body
    assert body["details"]["type"] == "inline"
    assert body["details"]["field_errors"][0]["field_name"] == "email"

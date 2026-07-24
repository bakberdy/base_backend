from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.integration_helpers import (
    auth_headers,
    count_active_sessions,
    create_authenticated_user,
    device_payload,
)

pytestmark = pytest.mark.integration


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={"email": email, "device": device_payload()},
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


def test_auth_flow_rotates_refresh_token_and_revokes_reused_token(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    if integration_settings.dev_otp_code is None:
        pytest.skip("Auth integration flow needs DEV_OTP_CODE in the test environment")

    email = f"integration-{uuid4().hex}@example.com"
    login_request_id = _login(integration_client, email)
    first_pair = _verify(
        integration_client, email, login_request_id, integration_settings.dev_otp_code
    )

    current_user_response = integration_client.get(
        "/users/me",
        headers=auth_headers(first_pair["access_token"]),
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
        headers=auth_headers(str(second_pair["access_token"])),
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
        headers=auth_headers(str(second_pair["access_token"])),
    )
    assert revoked_access_response.status_code == 401
    assert revoked_access_response.json()["code"] == 401


def test_login_validation_error_is_localized_at_api_boundary(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/auth/login",
        headers={"Accept-Language": "ru"},
        json={"email": "not-an-email", "device": device_payload("invalid-email-device")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Ошибка валидации"
    assert body["code"] == 422
    assert "message_key" not in body
    assert body["details"]["type"] == "inline"
    assert body["details"]["field_errors"][0]["field_name"] == "email"


def test_verify_email_rejects_invalid_and_reused_otp_requests(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    if integration_settings.dev_otp_code is None:
        pytest.skip("Auth integration flow needs DEV_OTP_CODE in the test environment")

    email = f"verify-{uuid4().hex}@example.com"
    login_request_id = _login(integration_client, email)
    invalid_code = "999999" if integration_settings.dev_otp_code == "000000" else "000000"

    invalid_response = integration_client.post(
        "/auth/verify-email",
        json={"email": email, "code": invalid_code, "login_request_id": login_request_id},
    )
    assert invalid_response.status_code == 400
    invalid_body = invalid_response.json()
    assert invalid_body["code"] == 400
    assert invalid_body["details"]["attempts_left"] == integration_settings.otp_max_attempts - 1

    _verify(integration_client, email, login_request_id, integration_settings.dev_otp_code)

    reused_response = integration_client.post(
        "/auth/verify-email",
        json={
            "email": email,
            "code": integration_settings.dev_otp_code,
            "login_request_id": login_request_id,
        },
    )
    assert reused_response.status_code == 410
    assert reused_response.json()["code"] == 410


def test_verify_email_rejects_unknown_login_request(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/auth/verify-email",
        json={
            "email": "unknown-login-request@example.com",
            "code": "111111",
            "login_request_id": "req_missing",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == 400


def test_refresh_rejects_malformed_token(integration_client: TestClient) -> None:
    response = integration_client.post("/auth/refresh", json={"refresh_token": "not-a-token"})

    assert response.status_code == 401
    assert response.json()["code"] == 401


def test_protected_auth_endpoints_require_authorization(integration_client: TestClient) -> None:
    responses = [
        integration_client.get("/auth/sessions"),
        integration_client.delete("/auth/sessions"),
        integration_client.patch("/auth/device/notifications", json={}),
        integration_client.post("/auth/logout"),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.json()["code"] == 401


def test_session_endpoints_and_device_notifications_work_with_real_persistence(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)

    list_response = integration_client.get(
        "/auth/sessions",
        headers=auth_headers(user.access_token),
    )
    assert list_response.status_code == 200
    sessions_body = list_response.json()
    assert sessions_body["pagination"]["total_items"] == 1
    session_id = sessions_body["items"][0]["id"]

    notifications_response = integration_client.patch(
        "/auth/device/notifications",
        headers=auth_headers(user.access_token),
        json={"push_provider": "firebase", "push_token": "integration-push-token"},
    )
    assert notifications_response.status_code == 200
    assert notifications_response.json() == {}

    revoke_session_response = integration_client.delete(
        f"/auth/sessions/{session_id}",
        headers=auth_headers(user.access_token),
    )
    assert revoke_session_response.status_code == 200
    assert revoke_session_response.json()["message"]

    already_revoked_response = integration_client.delete(
        f"/auth/sessions/{session_id}",
        headers=auth_headers(user.access_token),
    )
    assert already_revoked_response.status_code == 401

    revoked_access_response = integration_client.get(
        "/users/me",
        headers=auth_headers(user.access_token),
    )
    assert revoked_access_response.status_code == 401


def test_revoke_all_sessions_and_logout_revoke_access(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    first_user = create_authenticated_user(integration_client, integration_settings)
    assert count_active_sessions(integration_client, first_user.id) == 1

    revoke_all_response = integration_client.delete(
        "/auth/sessions",
        headers=auth_headers(first_user.access_token),
    )
    assert revoke_all_response.status_code == 200
    assert count_active_sessions(integration_client, first_user.id) == 0

    second_user = create_authenticated_user(integration_client, integration_settings)
    logout_response = integration_client.post(
        "/auth/logout",
        headers=auth_headers(second_user.access_token),
    )
    assert logout_response.status_code == 200
    assert count_active_sessions(integration_client, second_user.id) == 0


def test_revoke_unknown_session_returns_not_found(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)

    response = integration_client.delete(
        f"/auth/sessions/{uuid4()}",
        headers=auth_headers(user.access_token),
    )

    assert response.status_code == 404
    assert response.json()["code"] == 404

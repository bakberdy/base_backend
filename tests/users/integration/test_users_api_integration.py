from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.users.domain.enums import UserRole, UserStatus
from tests.integration_helpers import auth_headers, create_authenticated_user


pytestmark = pytest.mark.integration


def test_protected_user_endpoints_require_authorization(integration_client: TestClient) -> None:
    user_id = uuid4()
    responses = [
        integration_client.get("/users"),
        integration_client.get("/users/me"),
        integration_client.get(f"/users/{user_id}"),
        integration_client.patch(f"/users/{user_id}/role", json={"role": UserRole.ADMIN.value}),
        integration_client.patch(f"/users/{user_id}/status", json={"status": UserStatus.BLOCKED.value}),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.json()["code"] == 401


def test_users_me_requires_auth_and_returns_current_user(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)
    response = integration_client.get("/users/me", headers=auth_headers(user.access_token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["role"] == UserRole.USER.value
    assert body["status"] == UserStatus.ACTIVE.value


def test_users_list_enforces_permissions_and_pagination_validation(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    regular_user = create_authenticated_user(integration_client, integration_settings)

    forbidden_response = integration_client.get(
        "/users",
        headers=auth_headers(regular_user.access_token),
    )
    assert forbidden_response.status_code == 403

    super_admin = create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.SUPER_ADMIN,
    )
    create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    validation_response = integration_client.get(
        "/users",
        params={"page_number": 0, "limit": 101},
        headers=auth_headers(super_admin.access_token),
    )
    assert validation_response.status_code == 422

    success_response = integration_client.get(
        "/users",
        params={"page_number": 1, "limit": 10},
        headers=auth_headers(super_admin.access_token),
    )
    assert success_response.status_code == 200
    body = success_response.json()
    assert body["pagination"]["total_items"] >= 3
    assert len(body["items"]) >= 3


def test_users_get_by_id_success_not_found_and_forbidden_boundaries(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    super_admin = create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.SUPER_ADMIN,
    )
    admin = create_authenticated_user(integration_client, integration_settings, role=UserRole.ADMIN)
    target_user = create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    success_response = integration_client.get(
        f"/users/{target_user.id}",
        headers=auth_headers(admin.access_token),
    )
    assert success_response.status_code == 200
    assert success_response.json()["id"] == str(target_user.id)

    forbidden_response = integration_client.get(
        f"/users/{super_admin.id}",
        headers=auth_headers(admin.access_token),
    )
    assert forbidden_response.status_code == 403

    not_found_response = integration_client.get(
        f"/users/{uuid4()}",
        headers=auth_headers(super_admin.access_token),
    )
    assert not_found_response.status_code == 404

    invalid_uuid_response = integration_client.get(
        "/users/not-a-uuid",
        headers=auth_headers(super_admin.access_token),
    )
    assert invalid_uuid_response.status_code == 422


def test_update_user_role_success_forbidden_not_found_and_validation(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    super_admin = create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.SUPER_ADMIN,
    )
    admin = create_authenticated_user(integration_client, integration_settings, role=UserRole.ADMIN)
    target_user = create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    forbidden_response = integration_client.patch(
        f"/users/{target_user.id}/role",
        headers=auth_headers(admin.access_token),
        json={"role": UserRole.ADMIN.value},
    )
    assert forbidden_response.status_code == 403

    validation_response = integration_client.patch(
        f"/users/{target_user.id}/role",
        headers=auth_headers(super_admin.access_token),
        json={"role": "owner"},
    )
    assert validation_response.status_code == 422

    not_found_response = integration_client.patch(
        f"/users/{uuid4()}/role",
        headers=auth_headers(super_admin.access_token),
        json={"role": UserRole.ADMIN.value},
    )
    assert not_found_response.status_code == 404

    success_response = integration_client.patch(
        f"/users/{target_user.id}/role",
        headers=auth_headers(super_admin.access_token),
        json={"role": UserRole.ADMIN.value},
    )
    assert success_response.status_code == 200
    assert success_response.json()["role"] == UserRole.ADMIN.value


def test_update_user_status_success_forbidden_not_found_and_validation(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    super_admin = create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.SUPER_ADMIN,
    )
    admin = create_authenticated_user(integration_client, integration_settings, role=UserRole.ADMIN)
    target_user = create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    forbidden_response = integration_client.patch(
        f"/users/{super_admin.id}/status",
        headers=auth_headers(admin.access_token),
        json={"status": UserStatus.BLOCKED.value},
    )
    assert forbidden_response.status_code == 403

    validation_response = integration_client.patch(
        f"/users/{target_user.id}/status",
        headers=auth_headers(super_admin.access_token),
        json={"status": "paused"},
    )
    assert validation_response.status_code == 422

    not_found_response = integration_client.patch(
        f"/users/{uuid4()}/status",
        headers=auth_headers(super_admin.access_token),
        json={"status": UserStatus.BLOCKED.value},
    )
    assert not_found_response.status_code == 404

    success_response = integration_client.patch(
        f"/users/{target_user.id}/status",
        headers=auth_headers(admin.access_token),
        json={"status": UserStatus.BLOCKED.value},
    )
    assert success_response.status_code == 200
    assert success_response.json()["status"] == UserStatus.BLOCKED.value

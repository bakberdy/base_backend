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
        integration_client.get(f"/users/{user_id}/profile"),
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
    assert body["is_user_data_uploaded"] is False


def test_users_me_profile_requires_auth_and_returns_profile(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)

    missing_response = integration_client.get(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
    )
    assert missing_response.status_code == 404

    created_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={
            "full_name": "John Smith",
            "phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "7001234567"},
        },
    )
    assert created_response.status_code == 201

    profile_response = integration_client.get(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
    )
    assert profile_response.status_code == 200
    profile_body = profile_response.json()
    assert profile_body["full_name"] == "John Smith"
    assert profile_body["phone_number"]["country_code"] == "KZ"
    assert profile_body["phone_number"]["dial_code"] == "+7"
    assert profile_body["phone_number"]["number"] == "7001234567"
    assert profile_body["completed_at"] is not None


def test_users_me_profile_rejects_invalid_phone_number_format(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)

    create_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={
            "full_name": "John Smith",
            "phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "7 700 123 45 67"},
        },
    )
    assert create_response.status_code == 422
    create_body = create_response.json()
    assert create_body["code"] == 422
    assert create_body["details"]["field_errors"][0]["field_name"] == "phone_number.number"

    valid_profile_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={
            "full_name": "John Smith",
            "phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "7001234567"},
        },
    )
    assert valid_profile_response.status_code == 201

    update_response = integration_client.patch(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={"phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "77012345"}},
    )
    assert update_response.status_code == 422
    update_body = update_response.json()
    assert update_body["details"]["field_errors"][0]["field_name"] == "phone_number.number"


def test_profile_preferences_and_delete_request_flow(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    user = create_authenticated_user(integration_client, integration_settings)

    profile_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={
            "full_name": "John Smith",
            "phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "7001234567"},
        },
    )
    assert profile_response.status_code == 201
    profile_body = profile_response.json()
    assert profile_body["full_name"] == "John Smith"
    assert profile_body["phone_number"]["country_code"] == "KZ"
    assert profile_body["phone_number"]["dial_code"] == "+7"
    assert profile_body["phone_number"]["number"] == "7001234567"
    assert profile_body["completed_at"] is not None

    current_user_response = integration_client.get("/users/me", headers=auth_headers(user.access_token))
    assert current_user_response.status_code == 200
    assert current_user_response.json()["is_user_data_uploaded"] is True

    duplicate_profile_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={"full_name": "John Smith"},
    )
    assert duplicate_profile_response.status_code == 409

    updated_profile_response = integration_client.patch(
        "/users/me/profile",
        headers=auth_headers(user.access_token),
        json={
            "full_name": "John Updated",
            "phone_number": {"country_code": "KG", "dial_code": "+996", "number": "7001234567"},
        },
    )
    assert updated_profile_response.status_code == 200
    updated_profile_body = updated_profile_response.json()
    assert updated_profile_body["full_name"] == "John Updated"
    assert updated_profile_body["phone_number"]["country_code"] == "KG"
    assert updated_profile_body["phone_number"]["dial_code"] == "+996"
    assert updated_profile_body["phone_number"]["number"] == "7001234567"

    avatar_response = integration_client.put(
        "/users/me/avatar",
        headers=auth_headers(user.access_token),
        files={"avatar": ("avatar.png", b"avatar-content", "image/png")},
    )
    assert avatar_response.status_code == 200
    assert avatar_response.json()["avatar_url"] is not None

    remove_avatar_response = integration_client.delete(
        "/users/me/avatar",
        headers=auth_headers(user.access_token),
    )
    assert remove_avatar_response.status_code == 200
    assert remove_avatar_response.json()["avatar_url"] is None

    preferences_response = integration_client.post(
        "/users/me/preferences",
        headers=auth_headers(user.access_token),
        json={"language": "en", "theme": "system"},
    )
    assert preferences_response.status_code == 201
    assert preferences_response.json()["language"] == "en"

    updated_preferences_response = integration_client.patch(
        "/users/me/preferences",
        headers=auth_headers(user.access_token),
        json={"language": "ru", "push_notifications_enabled": False},
    )
    assert updated_preferences_response.status_code == 200
    updated_preferences = updated_preferences_response.json()
    assert updated_preferences["language"] == "ru"
    assert updated_preferences["push_notifications_enabled"] is False

    get_preferences_response = integration_client.get(
        "/users/me/preferences",
        headers=auth_headers(user.access_token),
    )
    assert get_preferences_response.status_code == 200
    assert get_preferences_response.json()["language"] == "ru"

    delete_request_response = integration_client.post(
        "/users/me/delete-request",
        headers=auth_headers(user.access_token),
    )
    assert delete_request_response.status_code == 200
    assert delete_request_response.json()["status"] == UserStatus.DELETION_REQUESTED.value


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
    create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.USER,
        email="z-user-sort@example.com",
    )
    create_authenticated_user(
        integration_client,
        integration_settings,
        role=UserRole.USER,
        email="a-user-sort@example.com",
    )

    invalid_query_params: list[dict[str, str | int]] = [
        {"page_number": 0},
        {"limit": 0},
        {"limit": 101},
        {"sorting_method": "oldest"},
        {"sort_key": ""},
    ]
    for params in invalid_query_params:
        validation_response = integration_client.get(
            "/users",
            params=params,
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
    assert body["pagination"]["total_items"] >= 4
    assert body["pagination"]["page"] == 1
    assert body["pagination"]["limit"] == 10
    assert len(body["items"]) >= 4

    sorted_response = integration_client.get(
        "/users",
        params={"page_number": 1, "limit": 2, "sorting_method": "asc", "sort_key": "email"},
        headers=auth_headers(super_admin.access_token),
    )
    assert sorted_response.status_code == 200
    sorted_emails = [item["email"] for item in sorted_response.json()["items"]]
    assert sorted_emails == sorted(sorted_emails)

    desc_sorted_response = integration_client.get(
        "/users",
        params={"page_number": 1, "limit": 2, "sorting_method": "desc", "sort_key": "email"},
        headers=auth_headers(super_admin.access_token),
    )
    assert desc_sorted_response.status_code == 200
    desc_sorted_emails = [item["email"] for item in desc_sorted_response.json()["items"]]
    assert desc_sorted_emails == sorted(desc_sorted_emails, reverse=True)

    status_response = integration_client.get(
        "/users",
        params={"status": UserStatus.ACTIVE.value},
        headers=auth_headers(super_admin.access_token),
    )
    assert status_response.status_code == 200
    assert all(item["status"] == UserStatus.ACTIVE.value for item in status_response.json()["items"])

    search_response = integration_client.get(
        "/users",
        params={"search": "a-user-sort"},
        headers=auth_headers(super_admin.access_token),
    )
    assert search_response.status_code == 200
    assert any(item["email"] == "a-user-sort@example.com" for item in search_response.json()["items"])

    invalid_sort_response = integration_client.get(
        "/users",
        params={"sort_key": "not_a_db_column"},
        headers=auth_headers(super_admin.access_token),
    )
    assert invalid_sort_response.status_code == 422
    assert invalid_sort_response.json()["message"] == "Invalid sort key"


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


def test_users_get_profile_by_id_success_not_found_and_forbidden_boundaries(
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
    regular_user = create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    created_response = integration_client.post(
        "/users/me/profile",
        headers=auth_headers(target_user.access_token),
        json={
            "full_name": "Managed User",
            "phone_number": {"country_code": "KZ", "dial_code": "+7", "number": "7001234567"},
        },
    )
    assert created_response.status_code == 201

    success_response = integration_client.get(
        f"/users/{target_user.id}/profile",
        headers=auth_headers(admin.access_token),
    )
    assert success_response.status_code == 200
    assert success_response.json()["user_id"] == str(target_user.id)
    assert success_response.json()["full_name"] == "Managed User"

    regular_user_response = integration_client.get(
        f"/users/{target_user.id}/profile",
        headers=auth_headers(regular_user.access_token),
    )
    assert regular_user_response.status_code == 403

    forbidden_response = integration_client.get(
        f"/users/{super_admin.id}/profile",
        headers=auth_headers(admin.access_token),
    )
    assert forbidden_response.status_code == 403

    missing_user_response = integration_client.get(
        f"/users/{uuid4()}/profile",
        headers=auth_headers(super_admin.access_token),
    )
    assert missing_user_response.status_code == 404
    assert missing_user_response.json()["message"] == "USER_NOT_FOUND"

    missing_profile_response = integration_client.get(
        f"/users/{admin.id}/profile",
        headers=auth_headers(super_admin.access_token),
    )
    assert missing_profile_response.status_code == 404
    assert missing_profile_response.json()["message"] == "USER_PROFILE_NOT_FOUND"


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


def test_admin_approve_deletion_request_soft_deletes_user(
    integration_client: TestClient,
    integration_settings: Any,
) -> None:
    admin = create_authenticated_user(integration_client, integration_settings, role=UserRole.ADMIN)
    target_user = create_authenticated_user(integration_client, integration_settings, role=UserRole.USER)

    invalid_approval_response = integration_client.post(
        f"/users/{target_user.id}/approve-deletion-request",
        headers=auth_headers(admin.access_token),
    )
    assert invalid_approval_response.status_code == 400

    request_response = integration_client.post(
        "/users/me/delete-request",
        headers=auth_headers(target_user.access_token),
    )
    assert request_response.status_code == 200
    assert request_response.json()["status"] == UserStatus.DELETION_REQUESTED.value

    approval_response = integration_client.post(
        f"/users/{target_user.id}/approve-deletion-request",
        headers=auth_headers(admin.access_token),
    )
    assert approval_response.status_code == 200
    assert approval_response.json()["status"] == UserStatus.DELETED.value

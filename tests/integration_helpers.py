import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.database import create_engine, create_session_maker
from app.modules.auth.infrastructure.sqlalchemy_models import UserSessionModel
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.infrastructure.sqlalchemy_models import UserModel


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    email: str
    access_token: str
    refresh_token: str


def device_payload(device_id: str | None = None) -> dict[str, str]:
    resolved_device_id = device_id or f"device-{uuid4().hex}"
    return {
        "device_id": resolved_device_id,
        "os": "ios",
        "os_version": "17.5",
        "model": "iPhone 15",
        "app_version": "1.0.0",
        "push_provider": "apns",
        "push_token": f"push-{resolved_device_id}",
    }


def auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def _run_db_operation(coro):
    async def runner():
        from app.core.config import get_settings

        settings = get_settings()
        engine = create_engine(
            settings.database_url_async,
            connect_timeout=settings.database_connect_timeout,
        )
        try:
            session_maker = create_session_maker(engine)
            async with session_maker() as session:
                return await coro(session)
        finally:
            await engine.dispose()

    return asyncio.run(runner())


def create_authenticated_user(
    client: TestClient,
    integration_settings: Any,
    *,
    role: UserRole = UserRole.USER,
    status: UserStatus = UserStatus.ACTIVE,
    email: str | None = None,
) -> AuthenticatedUser:
    if integration_settings.dev_otp_code is None:
        raise AssertionError("DEV_OTP_CODE is required for API integration auth helpers")

    resolved_email = email or f"integration-{uuid4().hex}@example.com"
    login_response = client.post(
        "/auth/login",
        json={"email": resolved_email, "device": device_payload()},
    )
    assert login_response.status_code == 202

    login_request_id = str(login_response.json()["login_request_id"])
    user_id = get_user_id_by_email(client, resolved_email)
    set_user_role_and_status(client, resolved_email, role=role, status=status)
    verify_response = client.post(
        "/auth/verify-email",
        json={
            "email": resolved_email,
            "code": integration_settings.dev_otp_code,
            "login_request_id": login_request_id,
        },
    )
    assert verify_response.status_code == 200
    token_pair = verify_response.json()

    return AuthenticatedUser(
        id=user_id,
        email=resolved_email,
        access_token=str(token_pair["access_token"]),
        refresh_token=str(token_pair["refresh_token"]),
    )


def get_user_id_by_email(_client: TestClient, email: str) -> UUID:
    async def query(session) -> UUID:
        result = await session.execute(select(UserModel.id).where(UserModel.email == email))
        return result.scalar_one()

    return _run_db_operation(query)


def set_user_role_and_status(
    _client: TestClient,
    email: str,
    *,
    role: UserRole,
    status: UserStatus,
) -> None:
    async def command(session) -> None:
        await session.execute(
            update(UserModel)
            .where(UserModel.email == email)
            .values(
                role=role.value,
                status=status.value,
                authorization_version=UserModel.authorization_version + 1,
            ),
        )
        await session.commit()

    _run_db_operation(command)


def count_active_sessions(_client: TestClient, user_id: UUID) -> int:
    async def query(session) -> int:
        result = await session.execute(
            select(UserSessionModel.id).where(
                UserSessionModel.user_id == user_id,
                UserSessionModel.revoked_at.is_(None),
            ),
        )
        return len(result.scalars().all())

    return _run_db_operation(query)

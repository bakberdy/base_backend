import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.auth.application.use_cases.validate_access_token import ValidateAccessTokenUseCase
from app.modules.auth.domain.entities import DeviceInfo, LoginRequest, UserSession
from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import InvalidTokenError, SessionNotFoundError, SessionRevokedError


class TokenServiceStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        raise NotImplementedError

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        raise NotImplementedError

    def decode_token(self, token: str) -> dict[str, object]:
        return self.payload


class AuthRepositoryStub:
    def __init__(self, session: UserSession | None) -> None:
        self.session = session

    async def get_session(self, session_id: UUID) -> UserSession | None:
        if self.session and self.session.id == session_id:
            return self.session
        return None

    async def lock_user_refresh(self, user_id: UUID) -> None:
        raise NotImplementedError

    async def upsert_user_device(self, *, user_id: UUID, device: DeviceInfo, now: datetime) -> UUID:
        raise NotImplementedError

    async def update_user_device_notifications(
        self,
        *,
        user_device_id: UUID,
        push_provider: str | None,
        push_token: str | None,
        now: datetime,
    ) -> None:
        raise NotImplementedError

    async def touch_user_device(self, user_device_id: UUID, at: datetime) -> None:
        raise NotImplementedError

    async def delete_pending_logins(self, user_id: UUID, user_device_id: UUID) -> None:
        raise NotImplementedError

    async def create_login_request(
        self,
        *,
        request_id: str,
        user_id: UUID,
        user_device_id: UUID,
        otp_hash: str,
        attempts_left: int,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        raise NotImplementedError

    async def get_login_request(self, request_id: str) -> LoginRequest | None:
        raise NotImplementedError

    async def mark_login_consumed(self, request_id: str, consumed_at: datetime) -> None:
        raise NotImplementedError

    async def update_login_attempts(self, request_id: str, attempts_left: int) -> None:
        raise NotImplementedError

    async def revoke_active_sessions_for_user_device(
        self, user_id: UUID, user_device_id: UUID, revoked_at: datetime
    ) -> None:
        raise NotImplementedError

    async def create_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        user_device_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        created_at: datetime,
        last_active_at: datetime,
    ) -> None:
        raise NotImplementedError

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None:
        raise NotImplementedError

    async def count_sessions_for_user(self, user_id: UUID, *, is_active: bool | None = None) -> int:
        raise NotImplementedError

    async def list_sessions_for_user(
        self, user_id: UUID, *, offset: int, limit: int, is_active: bool | None = None
    ) -> list[UserSession]:
        raise NotImplementedError

    async def revoke_session(self, session_id: UUID, user_id: UUID, revoked_at: datetime) -> bool:
        raise NotImplementedError

    async def revoke_session_by_id(self, session_id: UUID, revoked_at: datetime) -> None:
        raise NotImplementedError

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        raise NotImplementedError

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None:
        raise NotImplementedError


def make_session(*, user_id: UUID | None = None, revoked: bool = False) -> UserSession:
    now = datetime.now(UTC)
    return UserSession(
        id=uuid4(),
        user_id=user_id or uuid4(),
        user_device_id=uuid4(),
        refresh_token_hash="hash",
        expires_at=now + timedelta(days=1),
        created_at=now,
        last_active_at=now,
        revoked_at=now if revoked else None,
    )


def run_use_case(use_case: ValidateAccessTokenUseCase) -> tuple[UUID, UUID]:
    return asyncio.run(use_case.execute("access-token"))


def test_validate_access_token_returns_user_and_session_ids() -> None:
    session = make_session()
    payload: dict[str, object] = {"typ": TokenType.ACCESS.value, "sub": str(session.user_id), "sid": str(session.id)}
    use_case = ValidateAccessTokenUseCase(AuthRepositoryStub(session), TokenServiceStub(payload))

    user_id, session_id = run_use_case(use_case)

    assert user_id == session.user_id
    assert session_id == session.id


def test_validate_access_token_rejects_refresh_token_type() -> None:
    session = make_session()
    payload: dict[str, object] = {"typ": TokenType.REFRESH.value, "sub": str(session.user_id), "sid": str(session.id)}
    use_case = ValidateAccessTokenUseCase(AuthRepositoryStub(session), TokenServiceStub(payload))

    try:
        run_use_case(use_case)
    except InvalidTokenError:
        return

    raise AssertionError("refresh token payload must not pass access validation")


def test_validate_access_token_rejects_missing_session() -> None:
    session_id = uuid4()
    payload: dict[str, object] = {"typ": TokenType.ACCESS.value, "sub": str(uuid4()), "sid": str(session_id)}
    use_case = ValidateAccessTokenUseCase(AuthRepositoryStub(None), TokenServiceStub(payload))

    try:
        run_use_case(use_case)
    except SessionNotFoundError:
        return

    raise AssertionError("missing session must raise SessionNotFoundError")


def test_validate_access_token_rejects_revoked_session() -> None:
    session = make_session(revoked=True)
    payload: dict[str, object] = {"typ": TokenType.ACCESS.value, "sub": str(session.user_id), "sid": str(session.id)}
    use_case = ValidateAccessTokenUseCase(AuthRepositoryStub(session), TokenServiceStub(payload))

    try:
        run_use_case(use_case)
    except SessionRevokedError:
        return

    raise AssertionError("revoked session must raise SessionRevokedError")

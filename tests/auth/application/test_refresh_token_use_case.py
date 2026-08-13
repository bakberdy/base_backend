import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.common.pagination.schemas import SortingMethod
from app.modules.auth.application.dto import TokenPairDto
from app.modules.auth.application.use_cases.refresh_token import RefreshTokenUseCase
from app.modules.auth.domain.entities import DeviceInfo, LoginRequest, UserSession
from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import InvalidRefreshTokenError
from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus
from tests.access_state import AccessStateStoreSpy


class UnitOfWorkSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class TokenServiceStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.new_access_token = "new-access-token"
        self.new_refresh_token = "new-refresh-token"

    def create_access_token(
        self,
        user_id: UUID,
        session_id: UUID,
        role: UserRole,
        authorization_version: int,
    ) -> str:
        return self.new_access_token

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        return self.new_refresh_token

    def decode_token(self, token: str) -> dict[str, object]:
        return self.payload


class PasswordHasherStub:
    def __init__(self, *, refresh_matches: bool) -> None:
        self.refresh_matches = refresh_matches

    def hash_otp(self, code: str) -> str:
        raise NotImplementedError

    def verify_otp(self, code: str, hashed: str) -> bool:
        raise NotImplementedError

    def hash_refresh_token(self, token: str) -> str:
        return f"hashed:{token}"

    def verify_refresh_hash(self, token: str, stored_hex: str) -> bool:
        return self.refresh_matches


class AuthRepositorySpy:
    def __init__(self, session: UserSession | None) -> None:
        self.session = session
        self.locked_users: list[UUID] = []
        self.revoked_sessions: list[UUID] = []
        self.revoked_all_users: list[UUID] = []
        self.created_sessions: list[dict[str, object]] = []
        self.touched_devices: list[UUID] = []

    async def lock_user_refresh(self, user_id: UUID) -> None:
        self.locked_users.append(user_id)

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

    async def get_session(self, session_id: UUID) -> UserSession | None:
        raise NotImplementedError

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None:
        if self.session and self.session.id == session_id:
            return self.session
        return None

    async def count_sessions_for_user(self, user_id: UUID, *, is_active: bool | None = None) -> int:
        raise NotImplementedError

    async def list_sessions_for_user(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        is_active: bool | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[UserSession]:
        raise NotImplementedError

    async def revoke_session(self, session_id: UUID, user_id: UUID, revoked_at: datetime) -> bool:
        raise NotImplementedError

    async def revoke_session_by_id(self, session_id: UUID, revoked_at: datetime) -> None:
        self.revoked_sessions.append(session_id)

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        self.revoked_all_users.append(user_id)

    async def create_session(self, **kwargs: object) -> None:
        self.created_sessions.append(kwargs)

    async def touch_user_device(self, user_device_id: UUID, at: datetime) -> None:
        self.touched_devices.append(user_device_id)

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None:
        raise NotImplementedError


class UserRepositoryStub:
    def __init__(self, user_id: UUID) -> None:
        self.user = User(
            id=user_id,
            email="user@example.com",
            role=UserRole.USER,
            status=UserStatus.ACTIVE,
            is_verified=True,
            created_at=datetime.now(UTC),
        )

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.user if self.user.id == user_id else None


def make_session(user_id: UUID, session_id: UUID) -> UserSession:
    now = datetime.now(UTC)
    return UserSession(
        id=session_id,
        user_id=user_id,
        user_device_id=uuid4(),
        refresh_token_hash="stored-hash",
        expires_at=now + timedelta(days=1),
        created_at=now,
        last_active_at=now,
        revoked_at=None,
    )


def execute(use_case: RefreshTokenUseCase) -> TokenPairDto:
    return asyncio.run(use_case.execute("refresh-token"))


def test_refresh_token_rotates_session_and_commits() -> None:
    user_id = uuid4()
    session_id = uuid4()
    session = make_session(user_id, session_id)
    repository = AuthRepositorySpy(session)
    unit_of_work = UnitOfWorkSpy()
    payload = {
        "typ": TokenType.REFRESH.value,
        "sub": str(user_id),
        "jti": str(session_id),
        "exp": datetime.now(UTC).timestamp() + 60,
    }
    use_case = RefreshTokenUseCase(
        repository,
        UserRepositoryStub(user_id),
        TokenServiceStub(payload),
        AccessStateStoreSpy(),
        PasswordHasherStub(refresh_matches=True),
        unit_of_work,
        refresh_expire_days=14,
    )

    result = execute(use_case)

    assert result.access_token == "new-access-token"
    assert result.refresh_token == "new-refresh-token"
    assert repository.locked_users == [user_id]
    assert repository.revoked_sessions == [session_id]
    assert len(repository.created_sessions) == 1
    assert repository.touched_devices == [session.user_device_id]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


def test_refresh_token_reuse_revokes_active_sessions_and_commits() -> None:
    user_id = uuid4()
    missing_session_id = uuid4()
    repository = AuthRepositorySpy(None)
    unit_of_work = UnitOfWorkSpy()
    payload = {
        "typ": TokenType.REFRESH.value,
        "sub": str(user_id),
        "jti": str(missing_session_id),
        "exp": datetime.now(UTC).timestamp() + 60,
    }
    use_case = RefreshTokenUseCase(
        repository,
        UserRepositoryStub(user_id),
        TokenServiceStub(payload),
        AccessStateStoreSpy(),
        PasswordHasherStub(refresh_matches=True),
        unit_of_work,
        refresh_expire_days=14,
    )

    try:
        execute(use_case)
    except InvalidRefreshTokenError:
        pass
    else:
        raise AssertionError("refresh token reuse must raise InvalidRefreshTokenError")

    assert repository.revoked_all_users == [user_id]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0

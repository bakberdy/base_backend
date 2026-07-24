import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from app.common.pagination.schemas import SortingMethod
from app.modules.auth.application.dto import DeviceInfo, LoginResultDto, TokenPairDto
from app.modules.auth.application.use_cases.login_user import LoginUserUseCase
from app.modules.auth.application.use_cases.verify_email import VerifyEmailUseCase
from app.modules.auth.domain.entities import LoginRequest, UserSession
from app.modules.auth.domain.exceptions import InvalidOtpError
from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.domain.repositories import UserRepository


class UnitOfWorkSpy:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class PasswordHasherStub:
    def hash_otp(self, code: str) -> str:
        return f"otp:{code}"

    def verify_otp(self, code: str, hashed: str) -> bool:
        return hashed == self.hash_otp(code)

    def hash_refresh_token(self, token: str) -> str:
        return f"refresh:{token}"

    def verify_refresh_hash(self, token: str, stored_hex: str) -> bool:
        return stored_hex == self.hash_refresh_token(token)


class OtpProviderSpy:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.sent_codes: list[dict[str, object]] = []

    def generate_otp_code(self) -> str:
        return "654321"

    async def send_otp_code(self, *, email: str, code: str, expires_in_seconds: int) -> None:
        if self.fail_send:
            raise RuntimeError("email provider failed")
        self.sent_codes.append(
            {"email": email, "code": code, "expires_in_seconds": expires_in_seconds}
        )


class TokenServiceStub:
    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        return f"access:{user_id}:{session_id}"

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        return f"refresh:{user_id}:{session_id}"

    def decode_token(self, token: str) -> dict[str, object]:
        raise NotImplementedError


class UserRepositorySpy:
    def __init__(self, user: User) -> None:
        self.user = user
        self.verified_users: list[tuple[UUID, bool]] = []

    async def get_by_email(self, email: str) -> User | None:
        return self.user if self.user.email == email else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.user if self.user.id == user_id else None

    async def get_or_create(self, email: str, now: datetime) -> User:
        self.user.email = email
        return self.user

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        self.verified_users.append((user_id, value))
        self.user.is_verified = value


class AuthRepositorySpy:
    def __init__(self, user_device_id: UUID) -> None:
        self.user_device_id = user_device_id
        self.upserted_devices: list[dict[str, object]] = []
        self.revoked_devices: list[tuple[UUID, UUID]] = []
        self.created_sessions: list[dict[str, object]] = []
        self.touched_devices: list[UUID] = []

    async def lock_user_refresh(self, user_id: UUID) -> None:
        raise NotImplementedError

    async def upsert_user_device(self, *, user_id: UUID, device: DeviceInfo, now: datetime) -> UUID:
        self.upserted_devices.append({"user_id": user_id, "device": device, "now": now})
        return self.user_device_id

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
        self.touched_devices.append(user_device_id)

    async def revoke_active_sessions_for_user_device(
        self, user_id: UUID, user_device_id: UUID, revoked_at: datetime
    ) -> None:
        self.revoked_devices.append((user_id, user_device_id))

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
        self.created_sessions.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "user_device_id": user_device_id,
                "refresh_token_hash": refresh_token_hash,
                "expires_at": expires_at,
                "created_at": created_at,
                "last_active_at": last_active_at,
            }
        )

    async def get_session(self, session_id: UUID) -> UserSession | None:
        raise NotImplementedError

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None:
        raise NotImplementedError

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
        raise NotImplementedError

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        raise NotImplementedError

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None:
        raise NotImplementedError


class LoginRequestStoreSpy:
    def __init__(self, login_request: LoginRequest | None = None) -> None:
        self.login_request = login_request
        self.deleted_pending: list[tuple[UUID, UUID]] = []
        self.created_requests: list[dict[str, object]] = []
        self.deleted_requests: list[str] = []
        self.updated_attempts: list[tuple[str, int]] = []
        self.consumed_requests: list[tuple[str, datetime]] = []

    async def delete_pending_logins(self, user_id: UUID, user_device_id: UUID) -> None:
        self.deleted_pending.append((user_id, user_device_id))

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
        self.created_requests.append(
            {
                "request_id": request_id,
                "user_id": user_id,
                "user_device_id": user_device_id,
                "otp_hash": otp_hash,
                "attempts_left": attempts_left,
                "expires_at": expires_at,
                "created_at": created_at,
            }
        )
        self.login_request = LoginRequest(
            id=request_id,
            user_id=user_id,
            user_device_id=user_device_id,
            otp_hash=otp_hash,
            attempts_left=attempts_left,
            expires_at=expires_at,
            consumed_at=None,
        )

    async def get_login_request(self, request_id: str) -> LoginRequest | None:
        if self.login_request is None or self.login_request.id != request_id:
            return None
        return self.login_request

    async def mark_login_consumed(self, request_id: str, consumed_at: datetime) -> None:
        self.consumed_requests.append((request_id, consumed_at))
        if self.login_request is not None:
            self.login_request.consumed_at = consumed_at

    async def update_login_attempts(self, request_id: str, attempts_left: int) -> None:
        self.updated_attempts.append((request_id, attempts_left))
        if self.login_request is not None:
            self.login_request.attempts_left = attempts_left

    async def delete_login_request(self, request_id: str) -> None:
        self.deleted_requests.append(request_id)
        if self.login_request is not None and self.login_request.id == request_id:
            self.login_request = None


def make_user(*, email: str = "user@example.com", is_verified: bool = False) -> User:
    return User(
        id=uuid4(),
        email=email,
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        is_verified=is_verified,
        created_at=datetime.now(UTC),
    )


def make_device() -> DeviceInfo:
    return DeviceInfo(
        device_id="device-1",
        os="ios",
        os_version="17.0",
        model="iPhone",
        app_version="1.0.0",
    )


def execute_login(use_case: LoginUserUseCase, *, email: str = "USER@EXAMPLE.COM") -> LoginResultDto:
    return asyncio.run(use_case.execute(email, make_device()))


def execute_verify(
    use_case: VerifyEmailUseCase, *, email: str, code: str, request_id: str
) -> TokenPairDto:
    return asyncio.run(use_case.execute(email, code, request_id))


def test_login_user_writes_pending_otp_to_login_request_store() -> None:
    user = make_user()
    user_device_id = uuid4()
    auth_repository = AuthRepositorySpy(user_device_id)
    users = UserRepositorySpy(user)
    login_requests = LoginRequestStoreSpy()
    unit_of_work = UnitOfWorkSpy()
    otp_provider = OtpProviderSpy()
    use_case = LoginUserUseCase(
        auth_repository,
        login_requests,
        cast(UserRepository, users),
        PasswordHasherStub(),
        otp_provider,
        unit_of_work,
        otp_expire_seconds=300,
        otp_max_attempts=3,
        dev_otp_code=None,
    )

    result = execute_login(use_case)

    assert result.login_request_id.startswith("req_")
    assert login_requests.deleted_pending == [(user.id, user_device_id)]
    assert len(login_requests.created_requests) == 1
    created = login_requests.created_requests[0]
    assert created["request_id"] == result.login_request_id
    assert created["otp_hash"] == "otp:654321"
    assert created["attempts_left"] == 3
    assert otp_provider.sent_codes == [
        {"email": "user@example.com", "code": "654321", "expires_in_seconds": 300}
    ]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0


def test_login_user_deletes_redis_request_when_otp_send_fails() -> None:
    user = make_user()
    login_requests = LoginRequestStoreSpy()
    unit_of_work = UnitOfWorkSpy()
    use_case = LoginUserUseCase(
        AuthRepositorySpy(uuid4()),
        login_requests,
        cast(UserRepository, UserRepositorySpy(user)),
        PasswordHasherStub(),
        OtpProviderSpy(fail_send=True),
        unit_of_work,
        otp_expire_seconds=300,
        otp_max_attempts=3,
        dev_otp_code=None,
    )

    try:
        execute_login(use_case)
    except RuntimeError as exc:
        assert str(exc) == "email provider failed"
    else:
        raise AssertionError("Expected RuntimeError")

    assert len(login_requests.created_requests) == 1
    assert login_requests.deleted_requests == [login_requests.created_requests[0]["request_id"]]
    assert unit_of_work.commits == 0
    assert unit_of_work.rollbacks == 1


def test_verify_email_decrements_attempts_in_login_request_store_for_invalid_code() -> None:
    user = make_user(email="user@example.com")
    request_id = "req_existing"
    login_request = LoginRequest(
        id=request_id,
        user_id=user.id,
        user_device_id=uuid4(),
        otp_hash="otp:111111",
        attempts_left=3,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        consumed_at=None,
    )
    login_requests = LoginRequestStoreSpy(login_request)
    unit_of_work = UnitOfWorkSpy()
    use_case = VerifyEmailUseCase(
        AuthRepositorySpy(login_request.user_device_id),
        login_requests,
        cast(UserRepository, UserRepositorySpy(user)),
        TokenServiceStub(),
        PasswordHasherStub(),
        unit_of_work,
        refresh_expire_days=14,
        dev_otp_code=None,
    )

    try:
        execute_verify(use_case, email=user.email, code="222222", request_id=request_id)
    except InvalidOtpError:
        pass
    else:
        raise AssertionError("Expected InvalidOtpError")

    assert login_requests.updated_attempts == [(request_id, 2)]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 1


def test_verify_email_marks_login_request_consumed_and_creates_session() -> None:
    user = make_user(email="user@example.com", is_verified=False)
    user_device_id = uuid4()
    request_id = "req_existing"
    login_requests = LoginRequestStoreSpy(
        LoginRequest(
            id=request_id,
            user_id=user.id,
            user_device_id=user_device_id,
            otp_hash="otp:111111",
            attempts_left=3,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            consumed_at=None,
        )
    )
    auth_repository = AuthRepositorySpy(user_device_id)
    users = UserRepositorySpy(user)
    unit_of_work = UnitOfWorkSpy()
    use_case = VerifyEmailUseCase(
        auth_repository,
        login_requests,
        cast(UserRepository, users),
        TokenServiceStub(),
        PasswordHasherStub(),
        unit_of_work,
        refresh_expire_days=14,
        dev_otp_code=None,
    )

    result = execute_verify(
        use_case, email="USER@EXAMPLE.COM", code="111111", request_id=request_id
    )

    assert result.access_token.startswith(f"access:{user.id}:")
    assert result.refresh_token.startswith(f"refresh:{user.id}:")
    assert login_requests.consumed_requests[0][0] == request_id
    assert users.verified_users == [(user.id, True)]
    assert auth_repository.revoked_devices == [(user.id, user_device_id)]
    assert len(auth_repository.created_sessions) == 1
    assert auth_repository.touched_devices == [user_device_id]
    assert unit_of_work.commits == 1
    assert unit_of_work.rollbacks == 0

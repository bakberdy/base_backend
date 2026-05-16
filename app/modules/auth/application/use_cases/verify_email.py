import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.auth.application.dto import TokenPairDto, UnitOfWork
from app.modules.auth.domain.exceptions import (
    InvalidCredentialsError,
    InvalidLoginRequestError,
    InvalidOtpError,
    LoginRequestAlreadyUsedError,
    OtpExpiredError,
    TooManyAttemptsError,
)
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.domain.services import PasswordHasher, TokenService
from app.modules.users.domain.repositories import UserRepository


class VerifyEmailUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        user_repository: UserRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        unit_of_work: UnitOfWork,
        *,
        refresh_expire_days: int,
        dev_otp_code: str | None = None,
    ) -> None:
        self._auth = auth_repository
        self._users = user_repository
        self._tokens = token_service
        self._hasher = password_hasher
        self._unit_of_work = unit_of_work
        self._refresh_expire_days = refresh_expire_days
        self._dev_otp_code = dev_otp_code

    async def execute(self, email: str, code: str, login_request_id: str) -> TokenPairDto:
        normalized = email.strip().lower()
        now = datetime.now(UTC)
        try:
            login_request = await self._auth.get_login_request(login_request_id)
            if login_request is None:
                raise InvalidLoginRequestError()

            user = await self._users.get_by_id(login_request.user_id)
            if user is None or user.email != normalized:
                raise InvalidCredentialsError(attempts_left=login_request.attempts_left)

            if login_request.consumed_at is not None:
                raise LoginRequestAlreadyUsedError(attempts_left=login_request.attempts_left)
            if login_request.expires_at < now:
                raise OtpExpiredError()
            if login_request.attempts_left <= 0:
                raise TooManyAttemptsError()

            otp_ok = False
            if self._dev_otp_code is not None and len(code) == len(self._dev_otp_code):
                otp_ok = secrets.compare_digest(code, self._dev_otp_code)
            if not otp_ok:
                otp_ok = self._hasher.verify_otp(code, login_request.otp_hash)
            if not otp_ok:
                new_left = login_request.attempts_left - 1
                await self._auth.update_login_attempts(login_request_id, new_left)
                if new_left <= 0:
                    await self._unit_of_work.commit()
                    raise TooManyAttemptsError()
                await self._unit_of_work.commit()
                raise InvalidOtpError(attempts_left=new_left)

            await self._auth.mark_login_consumed(login_request_id, now)
            if not user.is_verified:
                await self._users.set_verified(user.id, True)
            await self._auth.revoke_active_sessions_for_user_device(user.id, login_request.user_device_id, now)

            session_id = uuid4()
            refresh_token = self._tokens.create_refresh_token(user.id, session_id)
            await self._auth.create_session(
                session_id=session_id,
                user_id=user.id,
                user_device_id=login_request.user_device_id,
                refresh_token_hash=self._hasher.hash_refresh_token(refresh_token),
                expires_at=now + timedelta(days=self._refresh_expire_days),
                created_at=now,
                last_active_at=now,
            )
            await self._auth.touch_user_device(login_request.user_device_id, now)
            access_token = self._tokens.create_access_token(user.id, session_id)
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise

        return TokenPairDto(access_token=access_token, refresh_token=refresh_token)

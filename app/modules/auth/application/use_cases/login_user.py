import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.auth.application.dto import DeviceInfo, LoginResultDto, UnitOfWork
from app.modules.auth.domain.repositories import AuthRepository, LoginRequestStore
from app.modules.auth.domain.services import OtpCodeProvider, PasswordHasher
from app.modules.users.domain.repositories import UserRepository

logger = logging.getLogger(__name__)


class LoginUserUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        login_request_store: LoginRequestStore,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        otp_provider: OtpCodeProvider,
        unit_of_work: UnitOfWork,
        *,
        otp_expire_seconds: int,
        otp_max_attempts: int,
        dev_otp_code: str | None = None,
    ) -> None:
        self._auth = auth_repository
        self._login_requests = login_request_store
        self._users = user_repository
        self._hasher = password_hasher
        self._otp_provider = otp_provider
        self._unit_of_work = unit_of_work
        self._otp_ttl = otp_expire_seconds
        self._otp_max = otp_max_attempts
        self._dev_otp_code = dev_otp_code

    async def execute(self, email: str, device: DeviceInfo) -> LoginResultDto:
        normalized = email.strip().lower()
        now = datetime.now(UTC)
        try:
            user = await self._users.get_or_create(normalized, now)
            user_device_id = await self._auth.upsert_user_device(user_id=user.id, device=device, now=now)
            await self._login_requests.delete_pending_logins(user.id, user_device_id)
            code = self._dev_otp_code if self._dev_otp_code else self._otp_provider.generate_otp_code()
            request_id = f"req_{uuid4().hex}"
            await self._login_requests.create_login_request(
                request_id=request_id,
                user_id=user.id,
                user_device_id=user_device_id,
                otp_hash=self._hasher.hash_otp(code),
                attempts_left=self._otp_max,
                expires_at=now + timedelta(seconds=self._otp_ttl),
                created_at=now,
            )
            await self._otp_provider.send_otp_code(
                email=normalized,
                code=code,
                expires_in_seconds=self._otp_ttl,
            )
            await self._unit_of_work.commit()
        except Exception:
            if "request_id" in locals():
                await self._login_requests.delete_login_request(request_id)
            await self._unit_of_work.rollback()
            raise

        logger.info("login otp email=%s request_id=%s", normalized, request_id)
        logger.debug("otp code=%s", code)
        return LoginResultDto(
            message_code="otp_sent_to_email",
            login_request_id=request_id,
            otp_expires_in=self._otp_ttl,
        )

from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.authorization.repositories import AccessStateStore, AuthorizationIdentityRepository
from app.core.config import get_settings
from app.core.database import SqlAlchemyUnitOfWork, get_db
from app.core.dependencies import (
    get_access_state_store,
    get_auth_repository,
    get_authorization_identity_repository,
)
from app.core.redis import get_redis
from app.modules.auth.application.use_cases.get_sessions import GetSessionsUseCase
from app.modules.auth.application.use_cases.login_user import LoginUserUseCase
from app.modules.auth.application.use_cases.logout_user import LogoutUserUseCase
from app.modules.auth.application.use_cases.refresh_token import RefreshTokenUseCase
from app.modules.auth.application.use_cases.revoke_all_tokens import RevokeAllTokensUseCase
from app.modules.auth.application.use_cases.revoke_token import RevokeTokenUseCase
from app.modules.auth.application.use_cases.update_device_notifications import (
    UpdateDeviceNotificationsUseCase,
)
from app.modules.auth.application.use_cases.verify_email import VerifyEmailUseCase
from app.modules.auth.domain.repositories import AuthRepository, LoginRequestStore
from app.modules.auth.domain.services import OtpCodeProvider, PasswordHasher, TokenService
from app.modules.auth.infrastructure.bcrypt_password_hasher import (
    BcryptPasswordHasher,
    SecureOtpCodeProvider,
)
from app.modules.auth.infrastructure.email_otp_provider import SmtpEmailOtpCodeProvider
from app.modules.auth.infrastructure.jwt_token_service import JwtTokenService
from app.modules.auth.infrastructure.redis_login_request_store import RedisLoginRequestStore


def get_login_request_store(redis: Redis = Depends(get_redis)) -> LoginRequestStore:
    return RedisLoginRequestStore(redis)


def get_password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


def get_otp_provider() -> OtpCodeProvider:
    settings = get_settings()
    if settings.otp_email_enabled:
        required = {
            "SMTP_HOST": settings.smtp_host,
            "SMTP_USERNAME": settings.smtp_username,
            "SMTP_PASSWORD": settings.smtp_password,
            "SMTP_SENDER_EMAIL": settings.smtp_sender_email,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing SMTP settings for OTP email delivery: {joined}")
        assert settings.smtp_host is not None
        assert settings.smtp_username is not None
        assert settings.smtp_password is not None
        assert settings.smtp_sender_email is not None
        return SmtpEmailOtpCodeProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            sender_email=settings.smtp_sender_email,
            sender_name=settings.smtp_sender_name,
            use_tls=settings.smtp_use_tls,
            use_ssl=settings.smtp_use_ssl,
        )
    return SecureOtpCodeProvider()


def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_expire_minutes=settings.access_token_expire_minutes,
        refresh_expire_days=settings.refresh_token_expire_days,
    )


def login_user_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    login_request_store: LoginRequestStore = Depends(get_login_request_store),
    user_repo: AuthorizationIdentityRepository = Depends(get_authorization_identity_repository),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    otp_provider: OtpCodeProvider = Depends(get_otp_provider),
) -> LoginUserUseCase:
    settings = get_settings()
    return LoginUserUseCase(
        auth_repo,
        login_request_store,
        user_repo,
        password_hasher,
        otp_provider,
        SqlAlchemyUnitOfWork(session),
        otp_expire_seconds=settings.otp_expire_seconds,
        otp_max_attempts=settings.otp_max_attempts,
        dev_otp_code=settings.dev_otp_code,
    )


def verify_email_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    login_request_store: LoginRequestStore = Depends(get_login_request_store),
    user_repo: AuthorizationIdentityRepository = Depends(get_authorization_identity_repository),
    token_service: TokenService = Depends(get_token_service),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> VerifyEmailUseCase:
    settings = get_settings()
    return VerifyEmailUseCase(
        auth_repo,
        login_request_store,
        user_repo,
        token_service,
        access_state_store,
        password_hasher,
        SqlAlchemyUnitOfWork(session),
        refresh_expire_days=settings.refresh_token_expire_days,
        dev_otp_code=settings.dev_otp_code,
    )


def refresh_token_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    user_repo: AuthorizationIdentityRepository = Depends(get_authorization_identity_repository),
    token_service: TokenService = Depends(get_token_service),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        auth_repo,
        user_repo,
        token_service,
        access_state_store,
        password_hasher,
        SqlAlchemyUnitOfWork(session),
        refresh_expire_days=get_settings().refresh_token_expire_days,
    )


def get_sessions_use_case(
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> GetSessionsUseCase:
    return GetSessionsUseCase(auth_repo)


def revoke_token_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
) -> RevokeTokenUseCase:
    return RevokeTokenUseCase(auth_repo, access_state_store, SqlAlchemyUnitOfWork(session))


def revoke_all_tokens_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
) -> RevokeAllTokensUseCase:
    return RevokeAllTokensUseCase(auth_repo, access_state_store, SqlAlchemyUnitOfWork(session))


def logout_user_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
) -> LogoutUserUseCase:
    return LogoutUserUseCase(auth_repo, access_state_store, SqlAlchemyUnitOfWork(session))


def update_device_notifications_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> UpdateDeviceNotificationsUseCase:
    return UpdateDeviceNotificationsUseCase(auth_repo, SqlAlchemyUnitOfWork(session))


LoginUserUseCaseDep = Annotated[LoginUserUseCase, Depends(login_user_use_case)]
VerifyEmailUseCaseDep = Annotated[VerifyEmailUseCase, Depends(verify_email_use_case)]
RefreshTokenUseCaseDep = Annotated[RefreshTokenUseCase, Depends(refresh_token_use_case)]
GetSessionsUseCaseDep = Annotated[GetSessionsUseCase, Depends(get_sessions_use_case)]
RevokeTokenUseCaseDep = Annotated[RevokeTokenUseCase, Depends(revoke_token_use_case)]
RevokeAllTokensUseCaseDep = Annotated[RevokeAllTokensUseCase, Depends(revoke_all_tokens_use_case)]
LogoutUserUseCaseDep = Annotated[LogoutUserUseCase, Depends(logout_user_use_case)]
UpdateDeviceNotificationsUseCaseDep = Annotated[
    UpdateDeviceNotificationsUseCase,
    Depends(update_device_notifications_use_case),
]

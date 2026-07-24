from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.responses.error_response import api_http_exception
from app.core.config import get_settings
from app.core.database import SqlAlchemyUnitOfWork, get_db
from app.modules.auth.application.use_cases.get_sessions import GetSessionsUseCase
from app.modules.auth.application.use_cases.login_user import LoginUserUseCase
from app.modules.auth.application.use_cases.logout_user import LogoutUserUseCase
from app.modules.auth.application.use_cases.refresh_token import RefreshTokenUseCase
from app.modules.auth.application.use_cases.revoke_all_tokens import RevokeAllTokensUseCase
from app.modules.auth.application.use_cases.revoke_token import RevokeTokenUseCase
from app.modules.auth.application.use_cases.update_device_notifications import (
    UpdateDeviceNotificationsUseCase,
)
from app.modules.auth.application.use_cases.validate_access_token import ValidateAccessTokenUseCase
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
from app.modules.auth.infrastructure.sqlalchemy_repositories import SqlAlchemyAuthRepository
from app.modules.users.api.dependencies import get_user_repository
from app.modules.users.domain.repositories import UserRepository

http_bearer = HTTPBearer(auto_error=False)


def get_auth_repository(session: AsyncSession = Depends(get_db)) -> AuthRepository:
    return SqlAlchemyAuthRepository(session)


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


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
    user_repo: UserRepository = Depends(get_user_repository),
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
    user_repo: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> VerifyEmailUseCase:
    settings = get_settings()
    return VerifyEmailUseCase(
        auth_repo,
        login_request_store,
        user_repo,
        token_service,
        password_hasher,
        SqlAlchemyUnitOfWork(session),
        refresh_expire_days=settings.refresh_token_expire_days,
        dev_otp_code=settings.dev_otp_code,
    )


def refresh_token_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    token_service: TokenService = Depends(get_token_service),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(
        auth_repo,
        token_service,
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
) -> RevokeTokenUseCase:
    return RevokeTokenUseCase(auth_repo, SqlAlchemyUnitOfWork(session))


def revoke_all_tokens_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> RevokeAllTokensUseCase:
    return RevokeAllTokensUseCase(auth_repo, SqlAlchemyUnitOfWork(session))


def logout_user_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> LogoutUserUseCase:
    return LogoutUserUseCase(auth_repo, SqlAlchemyUnitOfWork(session))


def update_device_notifications_use_case(
    session: AsyncSession = Depends(get_db),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> UpdateDeviceNotificationsUseCase:
    return UpdateDeviceNotificationsUseCase(auth_repo, SqlAlchemyUnitOfWork(session))


def validate_access_token_use_case(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    token_service: TokenService = Depends(get_token_service),
) -> ValidateAccessTokenUseCase:
    return ValidateAccessTokenUseCase(auth_repo, token_service)


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


async def get_current_session_context(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    use_case: Annotated[ValidateAccessTokenUseCase, Depends(validate_access_token_use_case)],
) -> tuple[UUID, UUID]:
    if creds is None or not creds.credentials:
        raise api_http_exception(status.HTTP_401_UNAUTHORIZED, "missing_authorization")
    return await use_case.execute(creds.credentials)


async def get_current_user_id(
    context: Annotated[tuple[UUID, UUID], Depends(get_current_session_context)],
) -> UUID:
    return context[0]


async def get_current_session_id(
    context: Annotated[tuple[UUID, UUID], Depends(get_current_session_context)],
) -> UUID:
    return context[1]


CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]
CurrentSessionIdDep = Annotated[UUID, Depends(get_current_session_id)]

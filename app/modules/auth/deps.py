from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthService
from app.modules.users.deps import get_user_repository
from app.modules.users.repository import UserRepository
from app.schemas.error import api_http_exception

http_bearer = HTTPBearer(auto_error=False)


def get_auth_repository(session: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(session)


def get_auth_service(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    settings = get_settings()
    return AuthService(
        auth_repo,
        user_repo,
        jwt_secret=settings.jwt_secret_key,
        jwt_algorithm=settings.jwt_algorithm,
        access_expire_minutes=settings.access_token_expire_minutes,
        refresh_expire_days=settings.refresh_token_expire_days,
        otp_expire_seconds=settings.otp_expire_seconds,
        otp_max_attempts=settings.otp_max_attempts,
        dev_otp_code=settings.dev_otp_code,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def _decode_access_payload(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
) -> dict[str, object]:
    if creds is None or not creds.credentials:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Missing authorization",
        )
    settings = get_settings()
    try:
        return decode_token(creds.credentials, settings.jwt_secret_key, [settings.jwt_algorithm])
    except ExpiredSignatureError:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Token expired",
        ) from None
    except PyJWTError:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        ) from None


async def get_validated_access_payload(
    payload: Annotated[dict[str, object], Depends(_decode_access_payload)],
    auth_repo: Annotated[AuthRepository, Depends(get_auth_repository)],
) -> dict[str, object]:
    if payload.get("typ") != "access":
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        )
    user_id = UUID(str(payload["sub"]))
    sid = payload.get("sid")
    if not isinstance(sid, str):
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        )
    try:
        session_id = UUID(sid)
    except ValueError as exc:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        ) from exc
    row = await auth_repo.get_session(session_id)
    if row is None:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Session not found",
        )
    if row.revoked_at is not None:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Session revoked",
        )
    if row.user_id != user_id:
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        )
    return payload


async def get_current_user_id(
    payload: Annotated[dict[str, object], Depends(get_validated_access_payload)],
) -> UUID:
    return UUID(str(payload["sub"]))


async def get_current_session_id(
    payload: Annotated[dict[str, object], Depends(get_validated_access_payload)],
) -> UUID:
    sid = payload["sid"]
    if not isinstance(sid, str):
        raise api_http_exception(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid token",
        )
    return UUID(sid)


CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]
CurrentSessionIdDep = Annotated[UUID, Depends(get_current_session_id)]

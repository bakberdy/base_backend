from typing import Annotated
from uuid import UUID

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.common.authorization.entities import CurrentPrincipal
from app.common.authorization.enums import UserRole
from app.common.authorization.repositories import AccessStateStore, AuthorizationIdentityRepository
from app.common.exceptions.base import ForbiddenError
from app.common.responses.error_response import api_http_exception
from app.core.config import get_settings
from app.core.dependencies import (
    get_access_state_store,
    get_auth_repository,
    get_authorization_identity_repository,
)
from app.modules.auth.application.use_cases.validate_access_token import ValidateAccessTokenUseCase
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.domain.services import TokenService
from app.modules.auth.infrastructure.jwt_token_service import JwtTokenService

http_bearer = HTTPBearer(auto_error=False)


def get_access_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        access_expire_minutes=settings.access_token_expire_minutes,
        refresh_expire_days=settings.refresh_token_expire_days,
    )


def validate_access_token_use_case(
    auth_repo: AuthRepository = Depends(get_auth_repository),
    identity_repo: AuthorizationIdentityRepository = Depends(get_authorization_identity_repository),
    token_service: TokenService = Depends(get_access_token_service),
    access_state_store: AccessStateStore = Depends(get_access_state_store),
) -> ValidateAccessTokenUseCase:
    return ValidateAccessTokenUseCase(
        auth_repo,
        identity_repo,
        token_service,
        access_state_store,
    )


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    use_case: Annotated[ValidateAccessTokenUseCase, Depends(validate_access_token_use_case)],
) -> CurrentPrincipal:
    if credentials is None or not credentials.credentials:
        raise api_http_exception(status.HTTP_401_UNAUTHORIZED, "missing_authorization")
    return await use_case.execute(credentials.credentials)


async def get_current_user_id(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> UUID:
    return principal.user_id


async def get_current_session_id(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> UUID:
    return principal.session_id


def require_roles(*allowed_roles: UserRole):
    async def dependency(
        principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    ) -> CurrentPrincipal:
        if principal.role not in allowed_roles:
            raise ForbiddenError()
        return principal

    return dependency


CurrentUserIdDep = Annotated[UUID, Depends(get_current_user_id)]
CurrentSessionIdDep = Annotated[UUID, Depends(get_current_session_id)]
CurrentPrincipalDep = Annotated[CurrentPrincipal, Depends(get_current_principal)]

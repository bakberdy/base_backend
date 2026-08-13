from datetime import UTC, datetime
from uuid import UUID

from app.common.authorization.entities import CurrentPrincipal
from app.common.authorization.enums import UserRole, UserStatus
from app.common.authorization.repositories import AccessStateStore, AuthorizationIdentityRepository
from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import (
    InvalidTokenError,
    SessionNotFoundError,
    SessionRevokedError,
)
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.domain.services import TokenService


class ValidateAccessTokenUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        user_repository: AuthorizationIdentityRepository,
        token_service: TokenService,
        access_state_store: AccessStateStore,
    ) -> None:
        self._auth = auth_repository
        self._users = user_repository
        self._tokens = token_service
        self._access_state = access_state_store

    async def execute(self, token: str) -> CurrentPrincipal:
        payload = self._tokens.decode_token(token)
        if payload.get("typ") != TokenType.ACCESS.value:
            raise InvalidTokenError()
        try:
            user_id = UUID(str(payload["sub"]))
            session_id = UUID(str(payload["sid"]))
            role = UserRole(str(payload["role"]))
            authorization_version = int(str(payload["av"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError() from exc
        if authorization_version < 1:
            raise InvalidTokenError()

        cached = await self._access_state.get(user_id, session_id)
        if cached.authorization_version is not None:
            if cached.authorization_version != authorization_version:
                raise InvalidTokenError()
        if cached.session_active is False:
            raise InvalidTokenError()
        if cached.authorization_version is not None and cached.session_active is True:
            return CurrentPrincipal(user_id, session_id, role, authorization_version)

        user = await self._users.get_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenError()
        if user.role != role or user.authorization_version != authorization_version:
            raise InvalidTokenError()

        session = await self._auth.get_session(session_id)
        if session is None:
            raise SessionNotFoundError()
        if session.revoked_at is not None or session.expires_at < datetime.now(UTC):
            raise SessionRevokedError()
        if session.user_id != user_id:
            raise InvalidTokenError()

        await self._access_state.cache(
            user_id=user_id,
            authorization_version=authorization_version,
            session_id=session_id,
            session_expires_at=session.expires_at,
        )
        return CurrentPrincipal(user_id, session_id, role, authorization_version)

from uuid import UUID

from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import InvalidTokenError, SessionNotFoundError, SessionRevokedError
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.domain.services import TokenService


class ValidateAccessTokenUseCase:
    def __init__(self, auth_repository: AuthRepository, token_service: TokenService) -> None:
        self._auth = auth_repository
        self._tokens = token_service

    async def execute(self, token: str) -> tuple[UUID, UUID]:
        payload = self._tokens.decode_token(token)
        if payload.get("typ") != TokenType.ACCESS.value:
            raise InvalidTokenError()
        user_id = UUID(str(payload["sub"]))
        sid = payload.get("sid")
        if not isinstance(sid, str):
            raise InvalidTokenError()
        try:
            session_id = UUID(sid)
        except ValueError as exc:
            raise InvalidTokenError() from exc
        row = await self._auth.get_session(session_id)
        if row is None:
            raise SessionNotFoundError()
        if row.revoked_at is not None:
            raise SessionRevokedError()
        if row.user_id != user_id:
            raise InvalidTokenError()
        return user_id, session_id

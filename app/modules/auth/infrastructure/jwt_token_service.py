from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, PyJWTError

from app.modules.auth.domain.exceptions import InvalidTokenError, TokenExpiredError
from app.modules.auth.domain.services import TokenService


class JwtTokenService(TokenService):
    def __init__(
        self,
        *,
        secret: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_days = refresh_expire_days

    def create_access_token(self, user_id: UUID, session_id: UUID) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "sid": str(session_id),
            "typ": "access",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=self._access_expire_minutes)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(user_id),
            "jti": str(session_id),
            "typ": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(days=self._refresh_expire_days)).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict[str, object]:
        try:
            result = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except ExpiredSignatureError as exc:
            raise TokenExpiredError() from exc
        except PyJWTError as exc:
            raise InvalidTokenError() from exc
        if not isinstance(result, dict):
            raise InvalidTokenError()
        return result

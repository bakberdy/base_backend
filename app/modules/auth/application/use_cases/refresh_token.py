from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.modules.auth.application.dto import TokenPairDto, UnitOfWork
from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import (
    InvalidRefreshTokenError,
    InvalidTokenError,
    TokenExpiredError,
)
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.domain.services import PasswordHasher, TokenService


class RefreshTokenUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        token_service: TokenService,
        password_hasher: PasswordHasher,
        unit_of_work: UnitOfWork,
        *,
        refresh_expire_days: int,
    ) -> None:
        self._auth = auth_repository
        self._tokens = token_service
        self._hasher = password_hasher
        self._unit_of_work = unit_of_work
        self._refresh_expire_days = refresh_expire_days

    async def _maybe_revoke_all_on_reuse(self, payload: dict[str, object], user_id: UUID) -> bool:
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return False
        if datetime.now(UTC).timestamp() < float(exp):
            await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))
            return True
        return False

    async def execute(self, refresh_token: str) -> TokenPairDto:
        payload = self._tokens.decode_token(refresh_token)
        if payload.get("typ") != TokenType.REFRESH.value:
            raise InvalidTokenError()
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["jti"]))

        committed_before_error = False
        try:
            await self._auth.lock_user_refresh(user_id)
            now = datetime.now(UTC)
            session = await self._auth.get_session_for_update(session_id)
            if session is None:
                if await self._maybe_revoke_all_on_reuse(payload, user_id):
                    await self._unit_of_work.commit()
                    committed_before_error = True
                raise InvalidRefreshTokenError()
            if session.user_id != user_id:
                await self._auth.revoke_all_active_for_user(user_id, now)
                await self._unit_of_work.commit()
                committed_before_error = True
                raise InvalidRefreshTokenError()
            if session.expires_at < now:
                await self._auth.revoke_session_by_id(session_id, now)
                await self._unit_of_work.commit()
                committed_before_error = True
                raise TokenExpiredError()
            if not self._hasher.verify_refresh_hash(refresh_token, session.refresh_token_hash):
                await self._auth.revoke_all_active_for_user(session.user_id, now)
                await self._unit_of_work.commit()
                committed_before_error = True
                raise InvalidRefreshTokenError()

            await self._auth.revoke_session_by_id(session_id, now)
            new_session_id = uuid4()
            new_refresh = self._tokens.create_refresh_token(user_id, new_session_id)
            await self._auth.create_session(
                session_id=new_session_id,
                user_id=user_id,
                user_device_id=session.user_device_id,
                refresh_token_hash=self._hasher.hash_refresh_token(new_refresh),
                expires_at=now + timedelta(days=self._refresh_expire_days),
                created_at=now,
                last_active_at=now,
            )
            await self._auth.touch_user_device(session.user_device_id, now)
            access_token = self._tokens.create_access_token(user_id, new_session_id)
            await self._unit_of_work.commit()
        except Exception:
            if not committed_before_error:
                await self._unit_of_work.rollback()
            raise

        return TokenPairDto(access_token=access_token, refresh_token=new_refresh)

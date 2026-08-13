from datetime import UTC, datetime
from uuid import UUID

from app.common.authorization.repositories import AccessStateStore
from app.modules.auth.application.dto import MessageResultDto, UnitOfWork
from app.modules.auth.domain.exceptions import ForbiddenSessionError, SessionNotFoundError
from app.modules.auth.domain.repositories import AuthRepository


class LogoutUserUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        access_state_store: AccessStateStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._auth = auth_repository
        self._access_state = access_state_store
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID, session_id: UUID) -> MessageResultDto:
        now = datetime.now(UTC)
        try:
            row = await self._auth.get_session(session_id)
            if row is None:
                raise SessionNotFoundError()
            if row.user_id != user_id:
                raise ForbiddenSessionError()
            if row.revoked_at is None:
                await self._auth.revoke_session_by_id(session_id, now)
            await self._access_state.revoke_session(user_id, session_id)
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return MessageResultDto(message_code="logged_out")

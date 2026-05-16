from datetime import UTC, datetime
from uuid import UUID

from app.modules.auth.application.dto import MessageResultDto, UnitOfWork
from app.modules.auth.domain.exceptions import ForbiddenSessionError, SessionAlreadyRevokedError, SessionNotFoundError
from app.modules.auth.domain.repositories import AuthRepository


class RevokeTokenUseCase:
    def __init__(self, auth_repository: AuthRepository, unit_of_work: UnitOfWork) -> None:
        self._auth = auth_repository
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID, session_id: UUID) -> MessageResultDto:
        now = datetime.now(UTC)
        try:
            ok = await self._auth.revoke_session(session_id, user_id, now)
            if not ok:
                row = await self._auth.get_session(session_id)
                if row is None:
                    raise SessionNotFoundError()
                if row.user_id != user_id:
                    raise ForbiddenSessionError()
                raise SessionAlreadyRevokedError()
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return MessageResultDto(message_code="session_deleted")

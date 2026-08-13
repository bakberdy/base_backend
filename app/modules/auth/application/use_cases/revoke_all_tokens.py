from datetime import UTC, datetime
from uuid import UUID

from app.common.authorization.repositories import AccessStateStore
from app.modules.auth.application.dto import MessageResultDto, UnitOfWork
from app.modules.auth.domain.repositories import AuthRepository


class RevokeAllTokensUseCase:
    def __init__(
        self,
        auth_repository: AuthRepository,
        access_state_store: AccessStateStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._auth = auth_repository
        self._access_state = access_state_store
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID) -> MessageResultDto:
        try:
            await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))
            await self._access_state.revoke_all_sessions(user_id)
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return MessageResultDto(message_code="all_sessions_deleted")

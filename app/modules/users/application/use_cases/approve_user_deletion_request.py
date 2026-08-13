from datetime import UTC, datetime
from uuid import UUID

from app.common.authorization.repositories import AccessStateStore, SessionRevocationRepository
from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.application.use_cases._permissions import ensure_can_manage_target
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.domain.exceptions import InvalidUserStatusTransitionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class ApproveUserDeletionRequestUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        auth_repository: SessionRevocationRepository,
        access_state_store: AccessStateStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._auth = auth_repository
        self._access_state = access_state_store
        self._unit_of_work = unit_of_work

    async def execute(self, actor_role: UserRole, user_id: UUID) -> UserDto:
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise UserNotFoundError()
        ensure_can_manage_target(actor_role, target)
        if target.status != UserStatus.DELETION_REQUESTED:
            raise InvalidUserStatusTransitionError()
        try:
            updated = await self._users.update_status(user_id, UserStatus.DELETED)
            if updated is None:
                await self._unit_of_work.rollback()
                raise UserNotFoundError()
            await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))
            await self._access_state.set_authorization_version(
                updated.id, updated.authorization_version
            )
            await self._access_state.revoke_all_sessions(user_id)
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserDto.from_entity(updated)

from datetime import UTC, datetime
from uuid import UUID

from app.modules.auth.domain.repositories import AuthRepository
from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.application.use_cases._permissions import ensure_can_manage_target, get_admin_actor
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.exceptions import InvalidUserStatusTransitionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class ApproveUserDeletionRequestUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        auth_repository: AuthRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._auth = auth_repository
        self._unit_of_work = unit_of_work

    async def execute(self, actor_id: UUID, user_id: UUID) -> UserDto:
        actor = await get_admin_actor(self._users, actor_id)
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise UserNotFoundError()
        ensure_can_manage_target(actor, target)
        if target.status != UserStatus.DELETION_REQUESTED:
            raise InvalidUserStatusTransitionError()
        try:
            updated = await self._users.update_status(user_id, UserStatus.DELETED)
            if updated is None:
                await self._unit_of_work.rollback()
                raise UserNotFoundError()
            await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserDto.from_entity(updated)

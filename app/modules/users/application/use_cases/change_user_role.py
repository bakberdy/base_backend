from uuid import UUID

from app.common.authorization.repositories import AccessStateStore
from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.exceptions import ForbiddenUserActionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class ChangeUserRoleUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        access_state_store: AccessStateStore,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._access_state = access_state_store
        self._unit_of_work = unit_of_work

    async def execute(self, actor_role: UserRole, user_id: UUID, role: UserRole) -> UserDto:
        if actor_role != UserRole.SUPER_ADMIN:
            raise ForbiddenUserActionError()
        try:
            updated = await self._users.update_role(user_id, role)
            if updated is None:
                raise UserNotFoundError()
            await self._access_state.set_authorization_version(
                updated.id, updated.authorization_version
            )
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserDto.from_entity(updated)

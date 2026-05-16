from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.application.use_cases._permissions import get_admin_actor
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.exceptions import ForbiddenUserActionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class ChangeUserRoleUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(self, actor_id: UUID, user_id: UUID, role: UserRole) -> UserDto:
        actor = await get_admin_actor(self._users, actor_id)
        if actor.role != UserRole.SUPER_ADMIN:
            raise ForbiddenUserActionError()
        updated = await self._users.update_role(user_id, role)
        if updated is None:
            await self._unit_of_work.rollback()
            raise UserNotFoundError()
        await self._unit_of_work.commit()
        return UserDto.from_entity(updated)

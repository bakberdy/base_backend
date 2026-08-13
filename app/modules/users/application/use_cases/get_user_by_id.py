from uuid import UUID

from app.modules.users.application.dto import UserDto
from app.modules.users.application.use_cases._permissions import ensure_can_manage_target
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.exceptions import UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class GetUserByIdUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, actor_role: UserRole, user_id: UUID) -> UserDto:
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise UserNotFoundError()
        ensure_can_manage_target(actor_role, target)
        return UserDto.from_entity(target)

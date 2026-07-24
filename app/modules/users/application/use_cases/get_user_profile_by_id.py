from uuid import UUID

from app.modules.users.application.dto import UserProfileDto
from app.modules.users.application.use_cases._permissions import (
    ensure_can_manage_target,
    get_admin_actor,
)
from app.modules.users.domain.exceptions import UserNotFoundError, UserProfileNotFoundError
from app.modules.users.domain.repositories import UserRepository


class GetUserProfileByIdUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, actor_id: UUID, user_id: UUID) -> UserProfileDto:
        actor = await get_admin_actor(self._users, actor_id)
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise UserNotFoundError()
        ensure_can_manage_target(actor, target)
        profile = await self._users.get_profile(user_id)
        if profile is None:
            raise UserProfileNotFoundError()
        return UserProfileDto.from_entity(profile)

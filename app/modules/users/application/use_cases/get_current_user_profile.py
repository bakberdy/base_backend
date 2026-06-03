from uuid import UUID

from app.modules.users.application.dto import UserProfileDto
from app.modules.users.domain.exceptions import UserProfileNotFoundError
from app.modules.users.domain.repositories import UserRepository


class GetCurrentUserProfileUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, user_id: UUID) -> UserProfileDto:
        profile = await self._users.get_profile(user_id)
        if profile is None:
            raise UserProfileNotFoundError()
        return UserProfileDto.from_entity(profile)

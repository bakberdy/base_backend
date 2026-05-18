from uuid import UUID

from app.modules.users.application.dto import UserPreferencesDto
from app.modules.users.domain.exceptions import UserPreferencesNotFoundError
from app.modules.users.domain.repositories import UserRepository


class GetUserPreferencesUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, user_id: UUID) -> UserPreferencesDto:
        preferences = await self._users.get_preferences(user_id)
        if preferences is None:
            raise UserPreferencesNotFoundError()
        return UserPreferencesDto.from_entity(preferences)

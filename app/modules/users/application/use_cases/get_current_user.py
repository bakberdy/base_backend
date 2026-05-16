from uuid import UUID

from app.modules.users.application.dto import UserDto
from app.modules.users.domain.exceptions import UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class GetCurrentUserUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, user_id: UUID) -> UserDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return UserDto.from_entity(user)

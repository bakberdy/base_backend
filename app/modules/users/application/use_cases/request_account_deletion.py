from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.exceptions import InvalidUserStatusTransitionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class RequestAccountDeletionUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID) -> UserDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise InvalidUserStatusTransitionError()
        try:
            updated = await self._users.update_status(user_id, UserStatus.DELETION_REQUESTED)
            if updated is None:
                await self._unit_of_work.rollback()
                raise UserNotFoundError()
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserDto.from_entity(updated)

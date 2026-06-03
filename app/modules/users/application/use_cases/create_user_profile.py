from datetime import UTC, datetime
from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserProfileDto
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.entities import PhoneNumber
from app.modules.users.domain.exceptions import (
    ForbiddenUserActionError,
    UserNotFoundError,
    UserProfileAlreadyExistsError,
)
from app.modules.users.domain.repositories import UserRepository


class CreateUserProfileUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        user_id: UUID,
        *,
        full_name: str,
        phone_number: PhoneNumber | None,
    ) -> UserProfileDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenUserActionError()
        existing = await self._users.get_profile(user_id)
        if existing is not None:
            raise UserProfileAlreadyExistsError()
        try:
            profile = await self._users.create_profile(
                user_id=user_id,
                full_name=full_name,
                phone_number=phone_number,
                now=datetime.now(UTC),
            )
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserProfileDto.from_entity(profile)

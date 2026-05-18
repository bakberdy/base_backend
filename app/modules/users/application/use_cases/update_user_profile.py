from datetime import UTC, datetime
from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserProfileDto
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.exceptions import ForbiddenUserActionError, UserNotFoundError, UserProfileNotFoundError
from app.modules.users.domain.repositories import UserRepository


class UpdateUserProfileUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        user_id: UUID,
        *,
        full_name: str | None = None,
        phone_number: str | None = None,
    ) -> UserProfileDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenUserActionError()
        try:
            profile = await self._users.update_profile(
                user_id=user_id,
                full_name=full_name,
                phone_number=phone_number,
                now=datetime.now(UTC),
            )
            if profile is None:
                await self._unit_of_work.rollback()
                raise UserProfileNotFoundError()
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserProfileDto.from_entity(profile)

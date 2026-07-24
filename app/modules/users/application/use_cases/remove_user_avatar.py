from datetime import UTC, datetime
from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserProfileDto
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.exceptions import (
    ForbiddenUserActionError,
    UserNotFoundError,
    UserProfileNotFoundError,
)
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.domain.services import AvatarStorageService


class RemoveUserAvatarUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        storage: AvatarStorageService,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._storage = storage
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID) -> UserProfileDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenUserActionError()
        profile = await self._users.get_profile(user_id)
        if profile is None:
            raise UserProfileNotFoundError()
        try:
            if profile.avatar_object_key is not None:
                await self._storage.delete_avatar(object_key=profile.avatar_object_key)
            updated = await self._users.clear_avatar(user_id=user_id, now=datetime.now(UTC))
            if updated is None:
                await self._unit_of_work.rollback()
                raise UserProfileNotFoundError()
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserProfileDto.from_entity(updated)

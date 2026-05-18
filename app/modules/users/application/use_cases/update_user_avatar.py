from datetime import UTC, datetime
from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserProfileDto
from app.modules.users.domain.enums import UserStatus
from app.modules.users.domain.exceptions import (
    ForbiddenUserActionError,
    InvalidAvatarUploadError,
    UserNotFoundError,
    UserProfileNotFoundError,
)
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.domain.services import AvatarStorageService

_ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_AVATAR_BYTES = 5 * 1024 * 1024


class UpdateUserAvatarUseCase:
    def __init__(
        self,
        user_repository: UserRepository,
        storage: AvatarStorageService,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._users = user_repository
        self._storage = storage
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        user_id: UUID,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> UserProfileDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenUserActionError()
        if content_type not in _ALLOWED_AVATAR_CONTENT_TYPES:
            raise InvalidAvatarUploadError("unsupported_content_type")
        if not content:
            raise InvalidAvatarUploadError("empty_file")
        if len(content) > _MAX_AVATAR_BYTES:
            raise InvalidAvatarUploadError("file_too_large")
        if await self._users.get_profile(user_id) is None:
            raise UserProfileNotFoundError()
        try:
            avatar_url, avatar_object_key = await self._storage.save_avatar(
                user_id=str(user_id),
                filename=filename,
                content_type=content_type,
                content=content,
            )
            profile = await self._users.update_avatar(
                user_id=user_id,
                avatar_url=avatar_url,
                avatar_object_key=avatar_object_key,
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

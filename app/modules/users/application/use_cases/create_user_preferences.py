from datetime import UTC, datetime
from uuid import UUID

from app.modules.users.application.dto import UnitOfWork, UserPreferencesDto
from app.modules.users.domain.enums import UserLanguage, UserStatus, UserTheme
from app.modules.users.domain.exceptions import (
    ForbiddenUserActionError,
    UserNotFoundError,
    UserPreferencesAlreadyExistsError,
)
from app.modules.users.domain.repositories import UserRepository


class CreateUserPreferencesUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(
        self,
        user_id: UUID,
        *,
        language: UserLanguage,
        theme: UserTheme,
        push_notifications_enabled: bool,
        email_notifications_enabled: bool,
        marketing_notifications_enabled: bool,
    ) -> UserPreferencesDto:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        if user.status != UserStatus.ACTIVE:
            raise ForbiddenUserActionError()
        if await self._users.get_preferences(user_id) is not None:
            raise UserPreferencesAlreadyExistsError()
        try:
            preferences = await self._users.create_preferences(
                user_id=user_id,
                language=language,
                theme=theme,
                push_notifications_enabled=push_notifications_enabled,
                email_notifications_enabled=email_notifications_enabled,
                marketing_notifications_enabled=marketing_notifications_enabled,
                now=datetime.now(UTC),
            )
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise
        return UserPreferencesDto.from_entity(preferences)

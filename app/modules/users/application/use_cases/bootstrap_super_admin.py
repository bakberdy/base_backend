from datetime import UTC, datetime

from app.modules.users.application.dto import UnitOfWork, UserDto
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.exceptions import UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


class BootstrapSuperAdminUseCase:
    def __init__(self, user_repository: UserRepository, unit_of_work: UnitOfWork) -> None:
        self._users = user_repository
        self._unit_of_work = unit_of_work

    async def execute(self, email: str) -> UserDto:
        normalized_email = email.strip().lower()
        user = await self._users.get_or_create(normalized_email, datetime.now(UTC))
        if user.role == UserRole.SUPER_ADMIN:
            await self._unit_of_work.commit()
            return UserDto.from_entity(user)

        updated = await self._users.update_role(user.id, UserRole.SUPER_ADMIN)
        if updated is None:
            await self._unit_of_work.rollback()
            raise UserNotFoundError()

        await self._unit_of_work.commit()
        return UserDto.from_entity(updated)

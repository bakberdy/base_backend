from uuid import UUID

from app.common.pagination.schemas import PaginationParams
from app.common.pagination.utils import build_pagination_meta, pagination_offset
from app.modules.users.application.dto import UserDto, UsersPageDto
from app.modules.users.application.use_cases._permissions import get_admin_actor
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.repositories import UserRepository


class GetUsersUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, actor_id: UUID, pagination: PaginationParams) -> UsersPageDto:
        actor = await get_admin_actor(self._users, actor_id)
        role_filter = None if actor.role == UserRole.SUPER_ADMIN else UserRole.USER
        total = await self._users.count_users(role=role_filter)
        rows = await self._users.list_users(
            offset=pagination_offset(pagination),
            limit=pagination.limit,
            role=role_filter,
        )
        return UsersPageDto(
            items=[UserDto.from_entity(user) for user in rows],
            pagination=build_pagination_meta(
                page=pagination.page_number,
                limit=pagination.limit,
                total_items=total,
            ),
        )

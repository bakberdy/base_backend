from uuid import UUID

from app.common.pagination.schemas import BaseListRequest
from app.common.pagination.utils import build_pagination_meta, pagination_offset
from app.modules.users.application.dto import UserDto, UsersPageDto
from app.modules.users.application.use_cases._permissions import get_admin_actor
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.repositories import UserRepository


class GetUsersUseCase:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def execute(self, actor_id: UUID, request: BaseListRequest) -> UsersPageDto:
        actor = await get_admin_actor(self._users, actor_id)
        role_filter = None if actor.role == UserRole.SUPER_ADMIN else UserRole.USER
        status_filter = getattr(request, "status", None)
        search = getattr(request, "search", None)
        total = await self._users.count_users(role=role_filter, status=status_filter, search=search)
        rows = await self._users.list_users(
            offset=pagination_offset(request),
            limit=request.limit,
            role=role_filter,
            status=status_filter,
            search=search,
            sort_key=request.sort_key,
            sorting_method=request.sorting_method,
        )
        return UsersPageDto(
            items=[UserDto.from_entity(user) for user in rows],
            pagination=build_pagination_meta(
                page=request.page_number,
                limit=request.limit,
                total_items=total,
            ),
        )

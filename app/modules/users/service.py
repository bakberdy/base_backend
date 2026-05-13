from uuid import UUID

from fastapi import status

from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserOut, UserRole, UserStatus
from app.schemas.error import api_http_exception
from app.schemas.pagination import (
    PaginatedResponse,
    PaginationParams,
    build_pagination_meta,
    pagination_offset,
)


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self._users = user_repo

    async def _get_actor(self, actor_id: UUID) -> User:
        actor = await self._users.get_by_id(actor_id)
        if actor is None:
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "User not found",
            )
        if actor.status != UserStatus.ACTIVE.value:
            raise api_http_exception(
                status.HTTP_403_FORBIDDEN,
                "Forbidden",
            )
        if actor.role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
            raise api_http_exception(
                status.HTTP_403_FORBIDDEN,
                "Forbidden",
            )
        return actor

    async def _get_target(self, user_id: UUID) -> User:
        target = await self._users.get_by_id(user_id)
        if target is None:
            raise api_http_exception(
                status.HTTP_404_NOT_FOUND,
                "User not found",
            )
        return target

    def _ensure_can_manage_target(self, actor: User, target: User) -> None:
        if actor.role == UserRole.SUPER_ADMIN.value:
            return
        if actor.role == UserRole.ADMIN.value and target.role == UserRole.USER.value:
            return
        raise api_http_exception(
            status.HTTP_403_FORBIDDEN,
            "Forbidden",
        )

    async def list_users(
        self,
        actor_id: UUID,
        pagination: PaginationParams,
    ) -> PaginatedResponse[UserOut]:
        actor = await self._get_actor(actor_id)
        role_filter = None if actor.role == UserRole.SUPER_ADMIN.value else UserRole.USER
        total = await self._users.count_users(role=role_filter)
        offset = pagination_offset(pagination)
        users = await self._users.list_users(
            offset=offset,
            limit=pagination.limit,
            role=role_filter,
        )
        return PaginatedResponse(
            items=[UserOut.model_validate(user) for user in users],
            pagination=build_pagination_meta(
                page=pagination.page_number,
                limit=pagination.limit,
                total_items=total,
            ),
        )

    async def get_user(self, actor_id: UUID, user_id: UUID) -> UserOut:
        actor = await self._get_actor(actor_id)
        target = await self._get_target(user_id)
        self._ensure_can_manage_target(actor, target)
        return UserOut.model_validate(target)

    async def update_role(self, actor_id: UUID, user_id: UUID, role: UserRole) -> UserOut:
        actor = await self._get_actor(actor_id)
        if actor.role != UserRole.SUPER_ADMIN.value:
            raise api_http_exception(
                status.HTTP_403_FORBIDDEN,
                "Forbidden",
            )
        target = await self._get_target(user_id)
        updated = await self._users.update_role(target.id, role)
        if updated is None:
            raise api_http_exception(
                status.HTTP_404_NOT_FOUND,
                "User not found",
            )
        return UserOut.model_validate(updated)

    async def update_status(self, actor_id: UUID, user_id: UUID, user_status: UserStatus) -> UserOut:
        actor = await self._get_actor(actor_id)
        target = await self._get_target(user_id)
        self._ensure_can_manage_target(actor, target)
        updated = await self._users.update_status(target.id, user_status)
        if updated is None:
            raise api_http_exception(
                status.HTTP_404_NOT_FOUND,
                "User not found",
            )
        return UserOut.model_validate(updated)

from uuid import UUID

from app.common.pagination.schemas import BaseListRequest
from app.common.pagination.utils import build_pagination_meta, pagination_offset
from app.modules.auth.application.dto import SessionDto, SessionsPageDto
from app.modules.auth.domain.repositories import AuthRepository


class GetSessionsUseCase:
    def __init__(self, auth_repository: AuthRepository) -> None:
        self._auth = auth_repository

    async def execute(
        self,
        user_id: UUID,
        request: BaseListRequest,
        *,
        is_active: bool | None = None,
    ) -> SessionsPageDto:
        total = await self._auth.count_sessions_for_user(user_id, is_active=is_active)
        rows = await self._auth.list_sessions_for_user(
            user_id,
            offset=pagination_offset(request),
            limit=request.limit,
            is_active=is_active,
            sort_key=request.sort_key,
            sorting_method=request.sorting_method,
        )
        return SessionsPageDto(
            items=[SessionDto.from_entity(row) for row in rows],
            pagination=build_pagination_meta(
                page=request.page_number,
                limit=request.limit,
                total_items=total,
            ),
        )

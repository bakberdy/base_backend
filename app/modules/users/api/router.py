from uuid import UUID

from fastapi import APIRouter

from app.common.pagination.schemas import BaseListDep, PaginatedResponse
from app.modules.auth.api.dependencies import CurrentUserIdDep
from app.modules.users.api.dependencies import (
    ChangeUserRoleUseCaseDep,
    ChangeUserStatusUseCaseDep,
    GetCurrentUserUseCaseDep,
    GetUserByIdUseCaseDep,
    GetUsersUseCaseDep,
)
from app.modules.users.api.schemas import UpdateUserRoleRequest, UpdateUserStatusRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])

ADMIN_ONLY_DESCRIPTION = "Only users with admin or super_admin roles can use this endpoint."
SUPER_ADMIN_ONLY_DESCRIPTION = "Only users with the super_admin role can use this endpoint."


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    description=ADMIN_ONLY_DESCRIPTION,
)
async def users_list(
    user_id: CurrentUserIdDep,
    request: BaseListDep,
    use_case: GetUsersUseCaseDep,
) -> PaginatedResponse[UserResponse]:
    result = await use_case.execute(user_id, request)
    return PaginatedResponse(
        items=[UserResponse.from_dto(item) for item in result.items],
        pagination=result.pagination,
    )


@router.get("/me", response_model=UserResponse)
async def users_me(user_id: CurrentUserIdDep, use_case: GetCurrentUserUseCaseDep) -> UserResponse:
    return UserResponse.from_dto(await use_case.execute(user_id))


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    description=ADMIN_ONLY_DESCRIPTION,
)
async def users_get(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    use_case: GetUserByIdUseCaseDep,
) -> UserResponse:
    return UserResponse.from_dto(await use_case.execute(current_user_id, user_id))


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    description=SUPER_ADMIN_ONLY_DESCRIPTION,
)
async def users_update_role(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    body: UpdateUserRoleRequest,
    use_case: ChangeUserRoleUseCaseDep,
) -> UserResponse:
    return UserResponse.from_dto(await use_case.execute(current_user_id, user_id, body.role))


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    description=ADMIN_ONLY_DESCRIPTION,
)
async def users_update_status(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    body: UpdateUserStatusRequest,
    use_case: ChangeUserStatusUseCaseDep,
) -> UserResponse:
    return UserResponse.from_dto(await use_case.execute(current_user_id, user_id, body.status))

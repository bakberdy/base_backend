from uuid import UUID

from fastapi import APIRouter, status

from app.modules.auth.deps import CurrentUserIdDep
from app.modules.users.deps import UserRepositoryDep, UserServiceDep
from app.modules.users.schemas import UpdateUserRoleBody, UpdateUserStatusBody, UserOut
from app.schemas.error import api_http_exception
from app.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=PaginatedResponse[UserOut])
async def users_list(
    user_id: CurrentUserIdDep,
    pagination: PaginationDep,
    svc: UserServiceDep,
) -> PaginatedResponse[UserOut]:
    return await svc.list_users(user_id, pagination)


@router.get("/me", response_model=UserOut)
async def users_me(user_id: CurrentUserIdDep, repo: UserRepositoryDep) -> UserOut:
    user = await repo.get_by_id(user_id)
    if user is None:
        raise api_http_exception(
            status.HTTP_404_NOT_FOUND,
            "user_not_found",
        )
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
async def users_get(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    svc: UserServiceDep,
) -> UserOut:
    return await svc.get_user(current_user_id, user_id)


@router.patch("/{user_id}/role", response_model=UserOut)
async def users_update_role(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    body: UpdateUserRoleBody,
    svc: UserServiceDep,
) -> UserOut:
    return await svc.update_role(current_user_id, user_id, body.role)


@router.patch("/{user_id}/status", response_model=UserOut)
async def users_update_status(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    body: UpdateUserStatusBody,
    svc: UserServiceDep,
) -> UserOut:
    return await svc.update_status(current_user_id, user_id, body.status)

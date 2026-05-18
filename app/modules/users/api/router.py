from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.common.pagination.schemas import PaginatedResponse, SortingMethod, build_base_list_request
from app.modules.auth.api.dependencies import CurrentUserIdDep
from app.modules.users.api.dependencies import (
    ApproveUserDeletionRequestUseCaseDep,
    ChangeUserRoleUseCaseDep,
    ChangeUserStatusUseCaseDep,
    CreateUserPreferencesUseCaseDep,
    CreateUserProfileUseCaseDep,
    GetCurrentUserUseCaseDep,
    GetUserPreferencesUseCaseDep,
    GetUserByIdUseCaseDep,
    GetUsersUseCaseDep,
    RequestAccountDeletionUseCaseDep,
    RemoveUserAvatarUseCaseDep,
    UpdateUserAvatarUseCaseDep,
    UpdateUserPreferencesUseCaseDep,
    UpdateUserProfileUseCaseDep,
)
from app.modules.users.api.schemas import (
    CreateUserPreferencesRequest,
    CreateUserProfileRequest,
    UpdateUserPreferencesRequest,
    UpdateUserProfileRequest,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UserListRequest,
    UserPreferencesResponse,
    UserProfileResponse,
    UserResponse,
)
from app.modules.users.domain.enums import UserStatus

router = APIRouter(prefix="/users", tags=["users"])

ADMIN_ONLY_DESCRIPTION = "Only users with admin or super_admin roles can use this endpoint."
SUPER_ADMIN_ONLY_DESCRIPTION = "Only users with the super_admin role can use this endpoint."


def get_user_list_request(
    page_number: int = Query(1, ge=1, alias="page_number"),
    limit: int = Query(20, ge=1, le=100, alias="limit"),
    sorting_method: SortingMethod = Query(SortingMethod.DESC, alias="sorting_method"),
    sort_key: str = Query("created_at", min_length=1, alias="sort_key"),
    status_filter: UserStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, min_length=1, max_length=255, alias="search"),
) -> UserListRequest:
    return build_base_list_request(
        UserListRequest,
        page_number=page_number,
        limit=limit,
        sorting_method=sorting_method,
        sort_key=sort_key,
        status=status_filter,
        search=search,
    )


UserListDep = Annotated[UserListRequest, Depends(get_user_list_request)]


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    description=ADMIN_ONLY_DESCRIPTION,
)
async def users_list(
    user_id: CurrentUserIdDep,
    request: UserListDep,
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


@router.post("/me/profile", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def users_create_profile(
    user_id: CurrentUserIdDep,
    body: CreateUserProfileRequest,
    use_case: CreateUserProfileUseCaseDep,
) -> UserProfileResponse:
    result = await use_case.execute(user_id, full_name=body.full_name, phone_number=body.phone_number)
    return UserProfileResponse.from_dto(result)


@router.patch("/me/profile", response_model=UserProfileResponse)
async def users_update_profile(
    user_id: CurrentUserIdDep,
    body: UpdateUserProfileRequest,
    use_case: UpdateUserProfileUseCaseDep,
) -> UserProfileResponse:
    result = await use_case.execute(
        user_id,
        full_name=body.full_name if "full_name" in body.model_fields_set else None,
        phone_number=body.phone_number if "phone_number" in body.model_fields_set else None,
    )
    return UserProfileResponse.from_dto(result)


@router.put("/me/avatar", response_model=UserProfileResponse)
async def users_update_avatar(
    user_id: CurrentUserIdDep,
    use_case: UpdateUserAvatarUseCaseDep,
    avatar: UploadFile = File(...),
) -> UserProfileResponse:
    content = await avatar.read()
    result = await use_case.execute(
        user_id,
        filename=avatar.filename or "avatar",
        content_type=avatar.content_type or "",
        content=content,
    )
    return UserProfileResponse.from_dto(result)


@router.delete("/me/avatar", response_model=UserProfileResponse)
async def users_remove_avatar(
    user_id: CurrentUserIdDep,
    use_case: RemoveUserAvatarUseCaseDep,
) -> UserProfileResponse:
    return UserProfileResponse.from_dto(await use_case.execute(user_id))


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def users_get_preferences(
    user_id: CurrentUserIdDep,
    use_case: GetUserPreferencesUseCaseDep,
) -> UserPreferencesResponse:
    return UserPreferencesResponse.from_dto(await use_case.execute(user_id))


@router.post("/me/preferences", response_model=UserPreferencesResponse, status_code=status.HTTP_201_CREATED)
async def users_create_preferences(
    user_id: CurrentUserIdDep,
    body: CreateUserPreferencesRequest,
    use_case: CreateUserPreferencesUseCaseDep,
) -> UserPreferencesResponse:
    result = await use_case.execute(
        user_id,
        language=body.language,
        theme=body.theme,
        push_notifications_enabled=body.push_notifications_enabled,
        email_notifications_enabled=body.email_notifications_enabled,
        marketing_notifications_enabled=body.marketing_notifications_enabled,
    )
    return UserPreferencesResponse.from_dto(result)


@router.patch("/me/preferences", response_model=UserPreferencesResponse)
async def users_update_preferences(
    user_id: CurrentUserIdDep,
    body: UpdateUserPreferencesRequest,
    use_case: UpdateUserPreferencesUseCaseDep,
) -> UserPreferencesResponse:
    result = await use_case.execute(
        user_id,
        language=body.language,
        theme=body.theme,
        push_notifications_enabled=body.push_notifications_enabled,
        email_notifications_enabled=body.email_notifications_enabled,
        marketing_notifications_enabled=body.marketing_notifications_enabled,
    )
    return UserPreferencesResponse.from_dto(result)


@router.post("/me/delete-request", response_model=UserResponse)
async def users_request_delete(
    user_id: CurrentUserIdDep,
    use_case: RequestAccountDeletionUseCaseDep,
) -> UserResponse:
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


@router.post(
    "/{user_id}/approve-deletion-request",
    response_model=UserResponse,
    summary="Admin only: approve user deletion request",
    description=ADMIN_ONLY_DESCRIPTION,
)
async def admin_users_approve_deletion_request(
    current_user_id: CurrentUserIdDep,
    user_id: UUID,
    use_case: ApproveUserDeletionRequestUseCaseDep,
) -> UserResponse:
    return UserResponse.from_dto(await use_case.execute(current_user_id, user_id))

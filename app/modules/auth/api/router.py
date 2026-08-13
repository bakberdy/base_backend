from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.common.localization.service import translate
from app.common.pagination.schemas import PaginatedResponse, SortingMethod, build_base_list_request
from app.core.authentication import CurrentSessionIdDep, CurrentUserIdDep
from app.core.config import get_settings
from app.core.security import limiter
from app.modules.auth.api.dependencies import (
    GetSessionsUseCaseDep,
    LoginUserUseCaseDep,
    LogoutUserUseCaseDep,
    RefreshTokenUseCaseDep,
    RevokeAllTokensUseCaseDep,
    RevokeTokenUseCaseDep,
    UpdateDeviceNotificationsUseCaseDep,
    VerifyEmailUseCaseDep,
)
from app.modules.auth.api.schemas import (
    DeviceNotificationsRequest,
    DeviceNotificationsResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    RevokeTokenResponse,
    SessionListRequest,
    SessionResponse,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_config = get_settings()


def get_session_list_request(
    page_number: int = Query(1, ge=1, alias="page_number"),
    limit: int = Query(20, ge=1, le=100, alias="limit"),
    sorting_method: SortingMethod = Query(SortingMethod.DESC, alias="sorting_method"),
    sort_key: str = Query("created_at", min_length=1, alias="sort_key"),
    is_active: bool | None = Query(None, alias="is_active"),
) -> SessionListRequest:
    return build_base_list_request(
        SessionListRequest,
        page_number=page_number,
        limit=limit,
        sorting_method=sorting_method,
        sort_key=sort_key,
        is_active=is_active,
    )


SessionListDep = Annotated[SessionListRequest, Depends(get_session_list_request)]


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_config.rate_limit_login)
async def auth_login(
    request: Request,
    body: LoginRequest,
    use_case: LoginUserUseCaseDep,
) -> LoginResponse:
    result = await use_case.execute(body.email, body.device.to_domain())
    return LoginResponse(
        message=translate(result.message_code),
        login_request_id=result.login_request_id,
        otp_expires_in=result.otp_expires_in,
    )


@router.post("/verify-email", response_model=VerifyResponse)
@limiter.limit(_config.rate_limit_verify)
async def auth_verify(
    request: Request,
    body: VerifyRequest,
    use_case: VerifyEmailUseCaseDep,
) -> VerifyResponse:
    result = await use_case.execute(body.email, body.code, body.login_request_id)
    return VerifyResponse(access_token=result.access_token, refresh_token=result.refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
async def auth_refresh(body: RefreshRequest, use_case: RefreshTokenUseCaseDep) -> RefreshResponse:
    result = await use_case.execute(body.refresh_token)
    return RefreshResponse(access_token=result.access_token, refresh_token=result.refresh_token)


@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def auth_list_sessions(
    user_id: CurrentUserIdDep,
    request: SessionListDep,
    use_case: GetSessionsUseCaseDep,
) -> PaginatedResponse[SessionResponse]:
    result = await use_case.execute(user_id, request, is_active=request.is_active)
    return PaginatedResponse(
        items=[SessionResponse.from_dto(item) for item in result.items],
        pagination=result.pagination,
    )


@router.delete("/sessions", response_model=RevokeTokenResponse)
async def auth_delete_all_sessions(
    user_id: CurrentUserIdDep,
    use_case: RevokeAllTokensUseCaseDep,
) -> RevokeTokenResponse:
    result = await use_case.execute(user_id)
    return RevokeTokenResponse(message=translate(result.message_code))


@router.delete("/sessions/{session_id}", response_model=RevokeTokenResponse)
async def auth_delete_session(
    session_id: UUID,
    user_id: CurrentUserIdDep,
    use_case: RevokeTokenUseCaseDep,
) -> RevokeTokenResponse:
    result = await use_case.execute(user_id, session_id)
    return RevokeTokenResponse(message=translate(result.message_code))


@router.patch("/device/notifications", response_model=DeviceNotificationsResponse)
async def auth_update_device_notifications(
    body: DeviceNotificationsRequest,
    user_id: CurrentUserIdDep,
    session_id: CurrentSessionIdDep,
    use_case: UpdateDeviceNotificationsUseCaseDep,
) -> DeviceNotificationsResponse:
    await use_case.execute(user_id, session_id, body.to_domain())
    return DeviceNotificationsResponse()


@router.post("/logout", response_model=LogoutResponse)
async def auth_logout(
    user_id: CurrentUserIdDep,
    session_id: CurrentSessionIdDep,
    use_case: LogoutUserUseCaseDep,
) -> LogoutResponse:
    result = await use_case.execute(user_id, session_id)
    return LogoutResponse(message=translate(result.message_code))

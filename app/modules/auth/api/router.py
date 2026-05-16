from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.common.localization.service import _
from app.common.pagination.schemas import PaginatedResponse, PaginationDep
from app.core.config import get_settings
from app.core.security import limiter
from app.modules.auth.api.dependencies import (
    CurrentSessionIdDep,
    CurrentUserIdDep,
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
    SessionResponse,
    VerifyRequest,
    VerifyResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_config = get_settings()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_config.rate_limit_login)
async def auth_login(
    request: Request,
    body: LoginRequest,
    use_case: LoginUserUseCaseDep,
) -> LoginResponse:
    result = await use_case.execute(body.email, body.device.to_domain())
    return LoginResponse(
        message=_(result.message_code),
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
    pagination: PaginationDep,
    use_case: GetSessionsUseCaseDep,
    is_active: bool | None = Query(None, alias="is_active"),
) -> PaginatedResponse[SessionResponse]:
    result = await use_case.execute(user_id, pagination, is_active=is_active)
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
    return RevokeTokenResponse(message=_(result.message_code))


@router.delete("/sessions/{session_id}", response_model=RevokeTokenResponse)
async def auth_delete_session(
    session_id: UUID,
    user_id: CurrentUserIdDep,
    use_case: RevokeTokenUseCaseDep,
) -> RevokeTokenResponse:
    result = await use_case.execute(user_id, session_id)
    return RevokeTokenResponse(message=_(result.message_code))


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
    return LogoutResponse(message=_(result.message_code))

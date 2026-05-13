from uuid import UUID

from fastapi import APIRouter, Query, Request, status

from app.core.config import get_settings
from app.core.limiter import limiter
from app.modules.auth.deps import (
    AuthServiceDep,
    CurrentSessionIdDep,
    CurrentUserIdDep,
)
from app.modules.auth.schemas import (
    DeviceNotificationsBody,
    DeviceNotificationsResponse,
    LoginBody,
    LoginResponse,
    LogoutResponse,
    RefreshBody,
    RefreshResponse,
    RevokeTokenResponse,
    SessionPublic,
    VerifyBody,
    VerifyResponse,
)
from app.schemas.pagination import PaginatedResponse, PaginationDep

router = APIRouter(prefix="/auth", tags=["auth"])

_config = get_settings()


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(_config.rate_limit_login)
async def auth_login(request: Request, body: LoginBody, svc: AuthServiceDep) -> LoginResponse:
    return await svc.login(body.email, body.device)


@router.post("/verify-email", response_model=VerifyResponse)
@limiter.limit(_config.rate_limit_verify)
async def auth_verify(
    request: Request,
    body: VerifyBody,
    svc: AuthServiceDep,
) -> VerifyResponse:
    return await svc.verify_email(body.email, body.code, body.login_request_id)


@router.post("/refresh", response_model=RefreshResponse)
async def auth_refresh(body: RefreshBody, svc: AuthServiceDep) -> RefreshResponse:
    return await svc.refresh_tokens(body.refresh_token)


@router.get("/sessions", response_model=PaginatedResponse[SessionPublic])
async def auth_list_sessions(
    user_id: CurrentUserIdDep,
    pagination: PaginationDep,
    svc: AuthServiceDep,
    is_active: bool | None = Query(None, alias="is_active"),
) -> PaginatedResponse[SessionPublic]:
    return await svc.list_sessions_for_user(user_id, pagination, is_active=is_active)


@router.delete("/sessions", response_model=RevokeTokenResponse)
async def auth_delete_all_sessions(
    user_id: CurrentUserIdDep,
    svc: AuthServiceDep,
) -> RevokeTokenResponse:
    return await svc.delete_all_sessions(user_id)


@router.delete("/sessions/{session_id}", response_model=RevokeTokenResponse)
async def auth_delete_session(
    session_id: UUID,
    user_id: CurrentUserIdDep,
    svc: AuthServiceDep,
) -> RevokeTokenResponse:
    await svc.revoke_session_by_session_id(user_id, session_id)
    return RevokeTokenResponse(message="session deleted")


@router.patch("/device/notifications", response_model=DeviceNotificationsResponse)
async def auth_update_device_notifications(
    body: DeviceNotificationsBody,
    user_id: CurrentUserIdDep,
    session_id: CurrentSessionIdDep,
    svc: AuthServiceDep,
) -> DeviceNotificationsResponse:
    return await svc.update_device_notifications(user_id, session_id, body)


@router.post("/logout", response_model=LogoutResponse)
async def auth_logout(
    user_id: CurrentUserIdDep,
    session_id: CurrentSessionIdDep,
    svc: AuthServiceDep,
) -> LogoutResponse:
    return await svc.logout(user_id, session_id)

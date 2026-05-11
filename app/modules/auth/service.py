import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import status
from jwt import ExpiredSignatureError, PyJWTError

from app.core.pagination import (
    PaginatedResponse,
    PaginationParams,
    build_pagination_meta,
    pagination_offset,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp_code,
    hash_otp,
    hash_refresh_token,
    verify_otp,
    verify_refresh_hash,
)
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AuthErrorDetails,
    DeviceInfo,
    DeviceNotificationsBody,
    DeviceNotificationsResponse,
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    RevokeTokenResponse,
    SessionPublic,
    VerifyResponse,
)
from app.modules.users.repository import UserRepository
from app.schemas.error import api_http_exception

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        auth_repo: AuthRepository,
        user_repo: UserRepository,
        *,
        jwt_secret: str,
        jwt_algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
        otp_expire_seconds: int,
        otp_max_attempts: int,
        dev_otp_code: str | None = None,
    ) -> None:
        self._auth = auth_repo
        self._users = user_repo
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._access_expire = access_expire_minutes
        self._refresh_expire = refresh_expire_days
        self._otp_ttl = otp_expire_seconds
        self._otp_max = otp_max_attempts
        self._dev_otp_code = dev_otp_code

    async def login(self, email: str, device: DeviceInfo) -> LoginResponse:
        normalized = email.strip().lower()
        now = datetime.now(UTC)
        user = await self._users.get_or_create(normalized, now)
        user_device_id = await self._auth.upsert_user_device(user_id=user.id, device=device, now=now)
        await self._auth.delete_pending_logins(user.id, user_device_id)
        code = self._dev_otp_code if self._dev_otp_code else generate_otp_code()
        req_id = f"req_{uuid4().hex}"
        hashed = hash_otp(code)
        expires = now + timedelta(seconds=self._otp_ttl)
        await self._auth.create_login_request(
            request_id=req_id,
            user_id=user.id,
            user_device_id=user_device_id,
            otp_hash=hashed,
            attempts_left=self._otp_max,
            expires_at=expires,
            created_at=now,
        )
        logger.info("login otp email=%s request_id=%s", normalized, req_id)
        logger.debug("otp code=%s", code)

        return LoginResponse(
            status="need_verification",
            message="OTP sent to email",
            login_request_id=req_id,
            otp_expires_in=self._otp_ttl,
        )

    async def verify_email(self, email: str, code: str, login_request_id: str) -> VerifyResponse:
        normalized = email.strip().lower()
        now = datetime.now(UTC)
        lr = await self._auth.get_login_request(login_request_id)
        if lr is None:
            raise api_http_exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                message="Invalid login request",
            )

        user = await self._users.get_by_id(lr.user_id)
        if user is None or user.email != normalized:
            raise api_http_exception(
                status.HTTP_400_BAD_REQUEST,
                "Invalid credentials",
                details=AuthErrorDetails(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    attempts_left=lr.attempts_left,
                ),
            )

        if lr.consumed_at is not None:
            raise api_http_exception(
                status.HTTP_410_GONE,
                "Login request already used",
                details=AuthErrorDetails(
                    status_code=status.HTTP_410_GONE,
                    attempts_left=lr.attempts_left,
                ),
            )

        if lr.expires_at < now:
            raise api_http_exception(
                status.HTTP_410_GONE,
                "OTP expired",
            )

        if lr.attempts_left <= 0:
            raise api_http_exception(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many attempts",
            )

        otp_ok = False
        if self._dev_otp_code is not None and len(code) == len(self._dev_otp_code):
            otp_ok = secrets.compare_digest(code, self._dev_otp_code)
        if not otp_ok:
            otp_ok = verify_otp(code, lr.otp_hash)
        if not otp_ok:
            new_left = lr.attempts_left - 1
            await self._auth.update_login_attempts(login_request_id, new_left)
            if new_left <= 0:
                raise api_http_exception(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many attempts",
                )
            raise api_http_exception(
                status.HTTP_400_BAD_REQUEST,
                "Invalid OTP",
                details=AuthErrorDetails(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    attempts_left=new_left,
                ),
            )

        await self._auth.mark_login_consumed(login_request_id, now)
        if not user.is_verified:
            await self._users.set_verified(user.id, True)

        await self._auth.revoke_active_sessions_for_user_device(user.id, lr.user_device_id, now)
        session_id = uuid4()
        refresh_plain = create_refresh_token(
            user.id,
            session_id,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expire_days=self._refresh_expire,
        )
        refresh_h = hash_refresh_token(refresh_plain)
        session_exp = now + timedelta(days=self._refresh_expire)
        await self._auth.create_session(
            session_id=session_id,
            user_id=user.id,
            user_device_id=lr.user_device_id,
            refresh_token_hash=refresh_h,
            expires_at=session_exp,
            created_at=now,
            last_active_at=now,
        )

        await self._auth.touch_user_device(lr.user_device_id, now)

        access = create_access_token(
            user.id,
            session_id,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expire_minutes=self._access_expire,
        )

        return VerifyResponse(status="success", access_token=access, refresh_token=refresh_plain)

    def _decode_refresh_payload(self, token: str) -> dict[str, object]:
        try:
            payload = decode_token(token, self._jwt_secret, [
                                   self._jwt_algorithm])
        except ExpiredSignatureError:
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Token expired",
            ) from None
        except PyJWTError:
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid token",
            ) from None
        return payload

    async def _maybe_revoke_all_on_reuse(self, payload: dict[str, object], user_id: UUID) -> None:
        exp = payload.get("exp")
        if not isinstance(exp, (int, float)):
            return
        if datetime.now(UTC).timestamp() >= float(exp):
            return
        await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))

    async def refresh_tokens(self, refresh_token: str) -> RefreshResponse:
        payload = self._decode_refresh_payload(refresh_token)
        if payload.get("typ") != "refresh":
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid token",
            )
        user_id = UUID(str(payload["sub"]))
        session_id = UUID(str(payload["jti"]))

        await self._auth.lock_user_refresh(user_id)
        now = datetime.now(UTC)

        row = await self._auth.get_session_for_update(session_id)
        if row is None:
            await self._maybe_revoke_all_on_reuse(payload, user_id)
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid refresh token",
            )

        if row.user_id != user_id:
            await self._auth.revoke_all_active_for_user(user_id, now)
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid refresh token",
            )

        if row.expires_at < now:
            await self._auth.revoke_session_by_id(session_id, now)
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Token expired",
            ) from None

        if not verify_refresh_hash(refresh_token, row.refresh_token_hash):
            await self._auth.revoke_all_active_for_user(user_id=row.user_id, revoked_at=now)
            raise api_http_exception(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid refresh token",
            ) from None

        await self._auth.revoke_session_by_id(session_id, now)

        new_session_id = uuid4()
        new_refresh = create_refresh_token(
            user_id,
            new_session_id,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expire_days=self._refresh_expire,
        )
        new_hash = hash_refresh_token(new_refresh)
        session_exp = now + timedelta(days=self._refresh_expire)
        await self._auth.create_session(
            session_id=new_session_id,
            user_id=user_id,
            user_device_id=row.user_device_id,
            refresh_token_hash=new_hash,
            expires_at=session_exp,
            created_at=now,
            last_active_at=now,
        )

        await self._auth.touch_user_device(row.user_device_id, now)

        access = create_access_token(
            user_id,
            new_session_id,
            secret=self._jwt_secret,
            algorithm=self._jwt_algorithm,
            expire_minutes=self._access_expire,
        )

        return RefreshResponse(access_token=access, refresh_token=new_refresh)

    async def revoke_session_by_session_id(self, user_id: UUID, session_id: UUID) -> None:
        now = datetime.now(UTC)
        ok = await self._auth.revoke_session(session_id, user_id, now)
        if not ok:
            row = await self._auth.get_session(session_id)
            if row is None:
                raise api_http_exception(
                    status.HTTP_404_NOT_FOUND,
                    "Session not found",
                )
            if row.user_id != user_id:
                raise api_http_exception(
                    status.HTTP_403_FORBIDDEN,
                    "Forbidden",
                )
            raise api_http_exception(
                status.HTTP_410_GONE,
                "Session already revoked",
            )

    async def list_sessions_for_user(
        self,
        user_id: UUID,
        pagination: PaginationParams,
        *,
        is_active: bool | None = None,
    ) -> PaginatedResponse[SessionPublic]:
        total = await self._auth.count_sessions_for_user(user_id, is_active=is_active)
        offset = pagination_offset(pagination)
        rows = await self._auth.list_sessions_for_user(
            user_id,
            offset=offset,
            limit=pagination.limit,
            is_active=is_active,
        )
        return PaginatedResponse(
            items=[SessionPublic.from_row(r) for r in rows],
            pagination=build_pagination_meta(
                page=pagination.page_number,
                limit=pagination.limit,
                total_items=total,
            ),
        )

    async def logout(self, user_id: UUID, session_id: UUID) -> LogoutResponse:
        now = datetime.now(UTC)
        row = await self._auth.get_session(session_id)
        if row is None:
            raise api_http_exception(
                status.HTTP_404_NOT_FOUND,
                "Session not found",
            )
        if row.user_id != user_id:
            raise api_http_exception(
                status.HTTP_403_FORBIDDEN,
                "Forbidden",
            )
        if row.revoked_at is None:
            await self._auth.revoke_session_by_id(session_id, now)
        return LogoutResponse(status="success", message="logged out")

    async def update_device_notifications(
        self,
        user_id: UUID,
        session_id: UUID,
        body: DeviceNotificationsBody,
    ) -> DeviceNotificationsResponse:
        now = datetime.now(UTC)
        if body.push_provider is None and body.push_token is None:
            return DeviceNotificationsResponse(status="success")
        row = await self._auth.get_session(session_id)
        if row is None:
            raise api_http_exception(
                status.HTTP_404_NOT_FOUND,
                "Session not found",
            )
        if row.user_id != user_id:
            raise api_http_exception(
                status.HTTP_403_FORBIDDEN,
                "Forbidden",
            )
        if row.revoked_at is not None:
            raise api_http_exception(
                status.HTTP_410_GONE,
                "Session revoked",
            )
        await self._auth.update_user_device_notifications(
            user_device_id=row.user_device_id,
            push_provider=body.push_provider,
            push_token=body.push_token,
            now=now,
        )
        return DeviceNotificationsResponse(status="success")

    async def delete_all_sessions(self, user_id: UUID) -> RevokeTokenResponse:
        await self._auth.revoke_all_active_for_user(user_id, datetime.now(UTC))
        return RevokeTokenResponse(status="success", message="all sessions deleted")

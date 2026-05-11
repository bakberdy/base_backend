from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.auth.models import LoginRequest, UserDevice, UserSession
from app.modules.auth.schemas import DeviceInfo


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_user_refresh(self, user_id: UUID) -> None:
        key = int.from_bytes(user_id.bytes[:8], "big", signed=False) % (2**31)
        await self._session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})

    async def upsert_user_device(self, *, user_id: UUID, device: DeviceInfo, now: datetime) -> UUID:
        row_id = uuid4()
        token_updated = now if device.push_token is not None else None
        insert_values = dict(
            id=row_id,
            user_id=user_id,
            client_device_id=device.device_id,
            os=device.os,
            os_version=device.os_version,
            model=device.model,
            app_version=device.app_version,
            push_provider=device.push_provider,
            push_token=device.push_token,
            push_token_updated_at=token_updated,
            last_seen_at=now,
            created_at=now,
        )
        set_on_conflict = {
            "os": device.os,
            "os_version": device.os_version,
            "model": device.model,
            "app_version": device.app_version,
            "last_seen_at": now,
        }
        if device.push_token is not None:
            set_on_conflict["push_token"] = device.push_token
            set_on_conflict["push_token_updated_at"] = now
        if device.push_provider is not None:
            set_on_conflict["push_provider"] = device.push_provider
        stmt = (
            insert(UserDevice)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=[UserDevice.user_id, UserDevice.client_device_id],
                set_=set_on_conflict,
            )
            .returning(UserDevice.id)
        )
        res = await self._session.execute(stmt)
        return res.scalar_one()

    async def update_user_device_notifications(
        self,
        *,
        user_device_id: UUID,
        push_provider: str | None,
        push_token: str | None,
        now: datetime,
    ) -> None:
        values: dict = {}
        if push_provider is not None:
            values["push_provider"] = push_provider
        if push_token is not None:
            values["push_token"] = push_token
            values["push_token_updated_at"] = now
        if not values:
            return
        stmt = update(UserDevice).where(UserDevice.id == user_device_id).values(**values)
        await self._session.execute(stmt)

    async def touch_user_device(self, user_device_id: UUID, at: datetime) -> None:
        stmt = update(UserDevice).where(UserDevice.id == user_device_id).values(last_seen_at=at)
        await self._session.execute(stmt)

    async def delete_pending_logins(self, user_id: UUID, user_device_id: UUID) -> None:
        stmt = delete(LoginRequest).where(
            LoginRequest.user_id == user_id,
            LoginRequest.user_device_id == user_device_id,
            LoginRequest.consumed_at.is_(None),
        )
        await self._session.execute(stmt)

    async def create_login_request(
        self,
        *,
        request_id: str,
        user_id: UUID,
        user_device_id: UUID,
        otp_hash: str,
        attempts_left: int,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        row = LoginRequest(
            id=request_id,
            user_id=user_id,
            user_device_id=user_device_id,
            otp_hash=otp_hash,
            attempts_left=attempts_left,
            expires_at=expires_at,
            consumed_at=None,
            created_at=created_at,
        )
        self._session.add(row)

    async def get_login_request(self, request_id: str) -> LoginRequest | None:
        stmt = select(LoginRequest).where(LoginRequest.id == request_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def mark_login_consumed(self, request_id: str, consumed_at: datetime) -> None:
        row = await self.get_login_request(request_id)
        if row is None:
            return
        row.consumed_at = consumed_at

    async def update_login_attempts(self, request_id: str, attempts_left: int) -> None:
        row = await self.get_login_request(request_id)
        if row is None:
            return
        row.attempts_left = attempts_left

    async def revoke_active_sessions_for_user_device(
        self, user_id: UUID, user_device_id: UUID, revoked_at: datetime
    ) -> None:
        stmt = (
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.user_device_id == user_device_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(stmt)

    async def create_session(
        self,
        *,
        session_id: UUID,
        user_id: UUID,
        user_device_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        created_at: datetime,
        last_active_at: datetime,
    ) -> None:
        row = UserSession(
            id=session_id,
            user_id=user_id,
            user_device_id=user_device_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            created_at=created_at,
            last_active_at=last_active_at,
            revoked_at=None,
        )
        self._session.add(row)

    async def get_session(self, session_id: UUID) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.id == session_id)
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None:
        stmt = (
            select(UserSession)
            .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
            .with_for_update()
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def count_sessions_for_user(self, user_id: UUID, *, is_active: bool | None = None) -> int:
        conditions = [UserSession.user_id == user_id]
        if is_active is True:
            conditions.append(UserSession.revoked_at.is_(None))
        elif is_active is False:
            conditions.append(UserSession.revoked_at.is_not(None))
        stmt = select(func.count()).select_from(UserSession).where(*conditions)
        res = await self._session.execute(stmt)
        return int(res.scalar_one() or 0)

    async def list_sessions_for_user(
        self, user_id: UUID, *, offset: int, limit: int, is_active: bool | None = None
    ) -> list[UserSession]:
        conditions = [UserSession.user_id == user_id]
        if is_active is True:
            conditions.append(UserSession.revoked_at.is_(None))
        elif is_active is False:
            conditions.append(UserSession.revoked_at.is_not(None))
        stmt = (
            select(UserSession)
            .options(selectinload(UserSession.user_device))
            .where(*conditions)
            .order_by(UserSession.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        res = await self._session.execute(stmt)
        return list(res.scalars().all())

    async def revoke_session(self, session_id: UUID, user_id: UUID, revoked_at: datetime) -> bool:
        stmt = (
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        res = await self._session.execute(stmt)
        return (res.rowcount or 0) > 0

    async def revoke_session_by_id(self, session_id: UUID, revoked_at: datetime) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(stmt)

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(stmt)

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None:
        stmt = (
            update(UserSession)
            .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
            .values(last_active_at=at)
        )
        await self._session.execute(stmt)

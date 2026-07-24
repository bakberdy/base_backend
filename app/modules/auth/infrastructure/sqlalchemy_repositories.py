from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.pagination.schemas import SortingMethod
from app.common.pagination.sqlalchemy import apply_sorting, model_sort_columns
from app.modules.auth.domain.entities import DeviceInfo, UserDevice, UserSession
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.infrastructure.sqlalchemy_models import (
    UserDeviceModel,
    UserSessionModel,
)


def _device_entity(model: UserDeviceModel) -> UserDevice:
    return UserDevice(
        id=model.id,
        client_device_id=model.client_device_id,
        os=model.os,
        os_version=model.os_version,
        model=model.model,
        app_version=model.app_version,
        push_provider=model.push_provider,
        push_token=model.push_token,
    )


def _session_entity(model: UserSessionModel, *, include_device: bool = False) -> UserSession:
    return UserSession(
        id=model.id,
        user_id=model.user_id,
        user_device_id=model.user_device_id,
        refresh_token_hash=model.refresh_token_hash,
        expires_at=model.expires_at,
        created_at=model.created_at,
        last_active_at=model.last_active_at,
        revoked_at=model.revoked_at,
        user_device=_device_entity(model.user_device)
        if include_device and model.user_device is not None
        else None,
    )


_SESSION_SORT_COLUMNS = model_sort_columns(UserSessionModel)


class SqlAlchemyAuthRepository(AuthRepository):
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
            insert(UserDeviceModel)
            .values(**insert_values)
            .on_conflict_do_update(
                index_elements=[UserDeviceModel.user_id, UserDeviceModel.client_device_id],
                set_=set_on_conflict,
            )
            .returning(UserDeviceModel.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

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
        if values:
            await self._session.execute(
                update(UserDeviceModel)
                .where(UserDeviceModel.id == user_device_id)
                .values(**values),
            )

    async def touch_user_device(self, user_device_id: UUID, at: datetime) -> None:
        await self._session.execute(
            update(UserDeviceModel)
            .where(UserDeviceModel.id == user_device_id)
            .values(last_seen_at=at),
        )

    async def revoke_active_sessions_for_user_device(
        self, user_id: UUID, user_device_id: UUID, revoked_at: datetime
    ) -> None:
        await self._session.execute(
            update(UserSessionModel)
            .where(
                UserSessionModel.user_id == user_id,
                UserSessionModel.user_device_id == user_device_id,
                UserSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at),
        )

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
        self._session.add(
            UserSessionModel(
                id=session_id,
                user_id=user_id,
                user_device_id=user_device_id,
                refresh_token_hash=refresh_token_hash,
                expires_at=expires_at,
                created_at=created_at,
                last_active_at=last_active_at,
                revoked_at=None,
            ),
        )

    async def get_session(self, session_id: UUID) -> UserSession | None:
        result = await self._session.execute(
            select(UserSessionModel).where(UserSessionModel.id == session_id)
        )
        row = result.scalar_one_or_none()
        return _session_entity(row) if row is not None else None

    async def get_session_for_update(self, session_id: UUID) -> UserSession | None:
        stmt = (
            select(UserSessionModel)
            .where(UserSessionModel.id == session_id, UserSessionModel.revoked_at.is_(None))
            .with_for_update()
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _session_entity(row) if row is not None else None

    async def count_sessions_for_user(self, user_id: UUID, *, is_active: bool | None = None) -> int:
        conditions = [UserSessionModel.user_id == user_id]
        if is_active is True:
            conditions.append(UserSessionModel.revoked_at.is_(None))
        elif is_active is False:
            conditions.append(UserSessionModel.revoked_at.is_not(None))
        result = await self._session.execute(
            select(func.count()).select_from(UserSessionModel).where(*conditions)
        )
        return int(result.scalar_one() or 0)

    async def list_sessions_for_user(
        self,
        user_id: UUID,
        *,
        offset: int,
        limit: int,
        is_active: bool | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[UserSession]:
        conditions = [UserSessionModel.user_id == user_id]
        if is_active is True:
            conditions.append(UserSessionModel.revoked_at.is_(None))
        elif is_active is False:
            conditions.append(UserSessionModel.revoked_at.is_not(None))
        stmt = apply_sorting(
            select(UserSessionModel)
            .options(selectinload(UserSessionModel.user_device))
            .where(*conditions),
            sort_key=sort_key,
            sorting_method=sorting_method,
            sort_columns=_SESSION_SORT_COLUMNS,
        )
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [_session_entity(row, include_device=True) for row in result.scalars().all()]

    async def revoke_session(self, session_id: UUID, user_id: UUID, revoked_at: datetime) -> bool:
        result = await self._session.execute(
            update(UserSessionModel)
            .where(
                UserSessionModel.id == session_id,
                UserSessionModel.user_id == user_id,
                UserSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at),
        )
        return (result.rowcount or 0) > 0

    async def revoke_session_by_id(self, session_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(UserSessionModel)
            .where(UserSessionModel.id == session_id, UserSessionModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at),
        )

    async def revoke_all_active_for_user(self, user_id: UUID, revoked_at: datetime) -> None:
        await self._session.execute(
            update(UserSessionModel)
            .where(UserSessionModel.user_id == user_id, UserSessionModel.revoked_at.is_(None))
            .values(revoked_at=revoked_at),
        )

    async def update_session_last_active(self, session_id: UUID, at: datetime) -> None:
        await self._session.execute(
            update(UserSessionModel)
            .where(UserSessionModel.id == session_id, UserSessionModel.revoked_at.is_(None))
            .values(last_active_at=at),
        )

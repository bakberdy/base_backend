from datetime import UTC, datetime
from uuid import UUID

from app.modules.auth.application.dto import DeviceNotifications, UnitOfWork
from app.modules.auth.domain.exceptions import (
    ForbiddenSessionError,
    SessionNotFoundError,
    SessionRevokedError,
)
from app.modules.auth.domain.repositories import AuthRepository


class UpdateDeviceNotificationsUseCase:
    def __init__(self, auth_repository: AuthRepository, unit_of_work: UnitOfWork) -> None:
        self._auth = auth_repository
        self._unit_of_work = unit_of_work

    async def execute(self, user_id: UUID, session_id: UUID, body: DeviceNotifications) -> None:
        if body.push_provider is None and body.push_token is None:
            return
        try:
            row = await self._auth.get_session(session_id)
            if row is None:
                raise SessionNotFoundError()
            if row.user_id != user_id:
                raise ForbiddenSessionError()
            if row.revoked_at is not None:
                raise SessionRevokedError()
            await self._auth.update_user_device_notifications(
                user_device_id=row.user_device_id,
                push_provider=body.push_provider,
                push_token=body.push_token,
                now=datetime.now(UTC),
            )
            await self._unit_of_work.commit()
        except Exception:
            await self._unit_of_work.rollback()
            raise

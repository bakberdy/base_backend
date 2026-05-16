from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserDeviceModel(Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "client_device_id", name="uq_user_devices_user_client"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    os: Mapped[str] = mapped_column(String(64), nullable=False)
    os_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    push_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    push_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    push_token_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    login_requests: Mapped[list[LoginRequestModel]] = relationship(back_populates="user_device")
    sessions: Mapped[list[UserSessionModel]] = relationship(back_populates="user_device")


class LoginRequestModel(Base):
    __tablename__ = "login_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    otp_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempts_left: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    user_device: Mapped[UserDeviceModel] = relationship(back_populates="login_requests")


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user_device: Mapped[UserDeviceModel] = relationship(back_populates="sessions")

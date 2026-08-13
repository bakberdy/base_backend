from typing import Protocol
from uuid import UUID

from app.common.authorization.enums import UserRole


class TokenService(Protocol):
    def create_access_token(
        self,
        user_id: UUID,
        session_id: UUID,
        role: UserRole,
        authorization_version: int,
    ) -> str: ...

    def create_refresh_token(self, user_id: UUID, session_id: UUID) -> str: ...

    def decode_token(self, token: str) -> dict[str, object]: ...


class PasswordHasher(Protocol):
    def hash_otp(self, code: str) -> str: ...

    def verify_otp(self, code: str, hashed: str) -> bool: ...

    def hash_refresh_token(self, token: str) -> str: ...

    def verify_refresh_hash(self, token: str, stored_hex: str) -> bool: ...


class OtpCodeProvider(Protocol):
    def generate_otp_code(self) -> str: ...

    async def send_otp_code(self, *, email: str, code: str, expires_in_seconds: int) -> None: ...

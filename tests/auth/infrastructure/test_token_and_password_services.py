import asyncio
import smtplib
from email.message import EmailMessage
from uuid import uuid4

import pytest

from app.common.exceptions.base import ApplicationError
from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import InvalidTokenError
from app.modules.auth.infrastructure.bcrypt_password_hasher import (
    BcryptPasswordHasher,
    SecureOtpCodeProvider,
)
from app.modules.auth.infrastructure.email_otp_provider import SmtpEmailOtpCodeProvider
from app.modules.auth.infrastructure.jwt_token_service import JwtTokenService
from app.modules.users.domain.enums import UserRole


def test_jwt_token_service_generates_access_and_refresh_payloads() -> None:
    user_id = uuid4()
    session_id = uuid4()
    service = JwtTokenService(
        secret="synthetic-test-secret-at-least-32-bytes",
        algorithm="HS256",
        access_expire_minutes=1,
        refresh_expire_days=14,
    )

    access_payload = service.decode_token(
        service.create_access_token(user_id, session_id, UserRole.ADMIN, 3)
    )
    refresh_payload = service.decode_token(service.create_refresh_token(user_id, session_id))

    assert access_payload["typ"] == TokenType.ACCESS.value
    assert access_payload["sub"] == str(user_id)
    assert access_payload["sid"] == str(session_id)
    assert access_payload["role"] == UserRole.ADMIN.value
    assert access_payload["av"] == 3
    assert refresh_payload["typ"] == TokenType.REFRESH.value
    assert refresh_payload["sub"] == str(user_id)
    assert refresh_payload["jti"] == str(session_id)


def test_jwt_token_service_rejects_invalid_token() -> None:
    service = JwtTokenService(
        secret="test-secret",
        algorithm="HS256",
        access_expire_minutes=1,
        refresh_expire_days=14,
    )

    try:
        service.decode_token("not-a-token")
    except InvalidTokenError:
        return

    raise AssertionError("invalid token must raise InvalidTokenError")


def test_password_hasher_verifies_otp_and_refresh_hashes() -> None:
    hasher = BcryptPasswordHasher()

    otp_hash = hasher.hash_otp("000000")
    refresh_hash = hasher.hash_refresh_token("refresh-token")

    assert hasher.verify_otp("000000", otp_hash)
    assert not hasher.verify_otp("111111", otp_hash)
    assert hasher.verify_refresh_hash("refresh-token", refresh_hash)
    assert not hasher.verify_refresh_hash("other-token", refresh_hash)


def test_secure_otp_code_provider_returns_six_digits() -> None:
    code = SecureOtpCodeProvider().generate_otp_code()

    assert len(code) == 6
    assert code.isdigit()


def test_email_otp_provider_sends_code_through_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, object] = {}

    class SmtpSpy:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = timeout

        def __enter__(self) -> "SmtpSpy":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def starttls(self, *, context: object) -> None:
            sent["starttls"] = context is not None

        def login(self, username: str, password: str) -> None:
            sent["username"] = username
            sent["password"] = password

        def send_message(self, message: object) -> None:
            sent["message"] = message

    monkeypatch.setattr("app.modules.auth.infrastructure.email_otp_provider.smtplib.SMTP", SmtpSpy)
    provider = SmtpEmailOtpCodeProvider(
        host="smtp.example.com",
        port=587,
        username="smtp-user",
        password="smtp-password",
        sender_email="no-reply@example.com",
        sender_name="Mobile App",
        use_tls=True,
        use_ssl=False,
    )

    asyncio.run(
        provider.send_otp_code(email="user@example.com", code="123456", expires_in_seconds=600)
    )

    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["username"] == "smtp-user"
    assert sent["password"] == "smtp-password"
    assert sent["starttls"] is True
    message = sent["message"]
    assert isinstance(message, EmailMessage)
    assert "123456" in message.get_content()


def test_email_otp_provider_wraps_smtp_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class SmtpFailure:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            raise smtplib.SMTPServerDisconnected("connection timed out")

    monkeypatch.setattr(
        "app.modules.auth.infrastructure.email_otp_provider.smtplib.SMTP", SmtpFailure
    )
    provider = SmtpEmailOtpCodeProvider(
        host="smtp.example.com",
        port=587,
        username="smtp-user",
        password="smtp-password",
        sender_email="no-reply@example.com",
        sender_name="Mobile App",
        use_tls=True,
        use_ssl=False,
    )

    with pytest.raises(ApplicationError) as exc_info:
        asyncio.run(
            provider.send_otp_code(email="user@example.com", code="123456", expires_in_seconds=600)
        )

    assert exc_info.value.code == "OTP_DELIVERY_FAILED"


def test_email_otp_provider_maps_rejected_recipient_to_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RejectedRecipientSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            pass

        def starttls(self, *, context) -> None:
            pass

        def login(self, username: str, password: str) -> None:
            pass

        def send_message(self, _message: EmailMessage) -> None:
            raise smtplib.SMTPRecipientsRefused(
                {"missing@example.com": (550, b"recipient verification failed")}
            )

    monkeypatch.setattr(
        "app.modules.auth.infrastructure.email_otp_provider.smtplib.SMTP",
        RejectedRecipientSmtp,
    )
    provider = SmtpEmailOtpCodeProvider(
        host="smtp.example.com",
        port=587,
        username="smtp-user",
        password="smtp-password",
        sender_email="no-reply@example.com",
        sender_name="Mobile App",
        use_tls=True,
        use_ssl=False,
    )

    with pytest.raises(ApplicationError) as exc_info:
        asyncio.run(
            provider.send_otp_code(
                email="missing@example.com",
                code="123456",
                expires_in_seconds=600,
            )
        )

    assert exc_info.value.code == "OTP_RECIPIENT_REJECTED"
    assert exc_info.value.details == {
        "type": "inline",
        "field_errors": [
            {
                "field_name": "email",
                "message": "otp_recipient_rejected",
            }
        ],
    }

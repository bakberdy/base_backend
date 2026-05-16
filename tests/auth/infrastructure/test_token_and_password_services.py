from uuid import uuid4

from app.modules.auth.domain.enums import TokenType
from app.modules.auth.domain.exceptions import InvalidTokenError
from app.modules.auth.infrastructure.bcrypt_password_hasher import BcryptPasswordHasher, SecureOtpCodeProvider
from app.modules.auth.infrastructure.jwt_token_service import JwtTokenService


def test_jwt_token_service_generates_access_and_refresh_payloads() -> None:
    user_id = uuid4()
    session_id = uuid4()
    service = JwtTokenService(
        secret="test-secret",
        algorithm="HS256",
        access_expire_minutes=1,
        refresh_expire_days=14,
    )

    access_payload = service.decode_token(service.create_access_token(user_id, session_id))
    refresh_payload = service.decode_token(service.create_refresh_token(user_id, session_id))

    assert access_payload["typ"] == TokenType.ACCESS.value
    assert access_payload["sub"] == str(user_id)
    assert access_payload["sid"] == str(session_id)
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

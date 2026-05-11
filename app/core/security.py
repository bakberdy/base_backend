import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt


def hash_otp(code: str) -> str:
    return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_otp(code: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_refresh_hash(token: str, stored_hex: str) -> bool:
    return hmac.compare_digest(hash_refresh_token(token), stored_hex)


def generate_otp_code() -> str:
    return f"{secrets.randbelow(900_000) + 100_000:06d}"


def create_access_token(
    user_id: UUID,
    session_id: UUID,
    *,
    secret: str,
    algorithm: str,
    expire_minutes: int,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_refresh_token(
    user_id: UUID,
    session_id: UUID,
    *,
    secret: str,
    algorithm: str,
    expire_days: int,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "jti": str(session_id),
        "typ": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=expire_days)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, secret: str, algorithms: list[str]) -> dict[str, object]:
    result = jwt.decode(token, secret, algorithms=algorithms)
    if not isinstance(result, dict):
        msg = "invalid payload"
        raise ValueError(msg)
    return result

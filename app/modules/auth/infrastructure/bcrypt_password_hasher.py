import hashlib
import hmac
import secrets

import bcrypt

from app.modules.auth.domain.services import OtpCodeProvider, PasswordHasher


class BcryptPasswordHasher(PasswordHasher):
    def hash_otp(self, code: str) -> str:
        return bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_otp(self, code: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(code.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    def hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def verify_refresh_hash(self, token: str, stored_hex: str) -> bool:
        return hmac.compare_digest(self.hash_refresh_token(token), stored_hex)


class SecureOtpCodeProvider(OtpCodeProvider):
    def generate_otp_code(self) -> str:
        return f"{secrets.randbelow(900_000) + 100_000:06d}"

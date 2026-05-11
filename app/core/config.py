import os
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_APP_ENV = frozenset({"development", "production"})
_raw_app_env = os.environ.get("APP_ENV", "development")
if _raw_app_env not in _VALID_APP_ENV:
    raise RuntimeError(
        f"APP_ENV must be one of {sorted(_VALID_APP_ENV)}, got {_raw_app_env!r}"
    )
_ENV_FILE = f"{_raw_app_env}.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "production"] = Field(default=_raw_app_env)

    database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/mobile_app"

    database_connect_timeout: float = 30.0
    database_reset_schema: bool = False

    jwt_secret_key: str = "change-me-in-production-use-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 5
    refresh_token_expire_days: int = 14
    otp_expire_seconds: int = 600
    otp_max_attempts: int = 5
    dev_otp_code: str | None = None
    rate_limit_login: str = "10/minute"
    rate_limit_verify: str = "20/minute"

    @property
    def database_url_async(self) -> str:
        url = self.database_url
        if url.startswith("postgresql+asyncpg://"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()

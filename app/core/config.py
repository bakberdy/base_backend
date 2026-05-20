import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "production"]

_VALID_ENVIRONMENTS = frozenset[str]({"development", "production"})
_environment = os.environ.get("ENVIRONMENT")
if _environment is None:
    raise RuntimeError("ENVIRONMENT must be set to development or production")
if _environment not in _VALID_ENVIRONMENTS:
    raise RuntimeError(
        f"ENVIRONMENT must be one of {sorted(_VALID_ENVIRONMENTS)}, got {_environment!r}"
    )

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / "config" / "run" / f"config.{_environment}.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Environment = Field(default=_environment)
    log_level: str = "INFO"
    cors_allowed_origins: str = ""
    cors_allow_credentials: bool = False

    database_url: str
    redis_url: str

    database_connect_timeout: float

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    otp_expire_seconds: int
    otp_max_attempts: int
    dev_otp_code: str | None = None
    otp_email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender_email: str | None = None
    smtp_sender_name: str = "Mobile App"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    rate_limit_login: str
    rate_limit_verify: str

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

    @property
    def database_name(self) -> str:
        return urlparse(self.database_url).path.lstrip("/")

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

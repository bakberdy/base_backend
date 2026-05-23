import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_environment = os.environ.get("ENVIRONMENT")
if _environment is None:
    raise RuntimeError("ENVIRONMENT must be set")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _PROJECT_ROOT / "config" / "run" / f"config.{_environment}.env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: str = Field(default=_environment)
    log_level: str
    cors_allowed_origins: str
    cors_allow_credentials: bool

    postgres_scheme: str
    postgres_async_scheme: str
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    redis_scheme: str
    redis_host: str
    redis_port: int
    redis_db: int
    database_url_value: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url_value: str | None = Field(default=None, validation_alias="REDIS_URL")

    database_connect_timeout: float

    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    otp_expire_seconds: int
    otp_max_attempts: int
    dev_otp_code: str | None
    otp_email_enabled: bool
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_sender_email: str | None
    smtp_sender_name: str
    smtp_use_tls: bool
    smtp_use_ssl: bool
    rate_limit_login: str
    rate_limit_verify: str
    app_title: str
    app_description: str
    health_status: str

    @property
    def database_url(self) -> str:
        if self.database_url_value:
            return self.database_url_value
        return (
            f"{self.postgres_scheme}://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_url_value:
            return self.redis_url_value
        return f"{self.redis_scheme}://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def database_url_async(self) -> str:
        parsed_url = urlparse(self.database_url)
        return urlunparse(parsed_url._replace(scheme=self.postgres_async_scheme))

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

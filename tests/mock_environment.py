import os

MOCK_ENVIRONMENT = {
    "ENVIRONMENT": "test",
    "LOG_LEVEL": "INFO",
    "CORS_ALLOWED_ORIGINS": "http://testserver",
    "CORS_ALLOW_CREDENTIALS": "false",
    "POSTGRES_SCHEME": "postgresql",
    "POSTGRES_ASYNC_SCHEME": "postgresql+asyncpg",
    "POSTGRES_HOST": "127.0.0.1",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": "mobile_app_test",
    "REDIS_SCHEME": "redis",
    "REDIS_HOST": "127.0.0.1",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "DATABASE_CONNECT_TIMEOUT": "5",
    "JWT_SECRET_KEY": "synthetic-mock-jwt-secret-key-32-bytes",
    "JWT_ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "1",
    "REFRESH_TOKEN_EXPIRE_DAYS": "14",
    "OTP_EXPIRE_SECONDS": "600",
    "OTP_MAX_ATTEMPTS": "5",
    "DEV_OTP_CODE": "000000",
    "OTP_EMAIL_ENABLED": "false",
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "",
    "SMTP_PASSWORD": "",
    "SMTP_SENDER_EMAIL": "",
    "SMTP_SENDER_NAME": "Mock Backend",
    "SMTP_USE_TLS": "true",
    "SMTP_USE_SSL": "false",
    "RATE_LIMIT_LOGIN": "1000/minute",
    "RATE_LIMIT_VERIFY": "1000/minute",
    "APP_TITLE": "Mock Mobile App API",
    "APP_DESCRIPTION": "In-process settings for automated tests.",
    "HEALTH_STATUS": "ok",
}


def apply_mock_environment() -> None:
    os.environ.update(MOCK_ENVIRONMENT)


def main() -> None:
    apply_mock_environment()

    import uvicorn

    port = int(os.getenv("UVICORN_SMOKE_PORT", "8000"))
    uvicorn.run("main:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()

import logging
import sys
from contextvars import ContextVar, Token
from logging.config import dictConfig

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


def configure_logging(level: str) -> None:
    normalized_level = level.upper()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_id": {
                    "()": RequestIdFilter,
                },
            },
            "formatters": {
                "default": {
                    "format": (
                        "%(asctime)s %(levelname)s [%(name)s] "
                        "request_id=%(request_id)s %(message)s"
                    ),
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": "default",
                    "filters": ["request_id"],
                },
            },
            "root": {
                "level": normalized_level,
                "handlers": ["default"],
            },
            "loggers": {
                "uvicorn.access": {
                    "level": "WARNING",
                    "handlers": ["default"],
                    "propagate": False,
                },
            },
        },
    )

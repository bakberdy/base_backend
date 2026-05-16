from __future__ import annotations

import json
from contextvars import ContextVar, Token
from functools import lru_cache
from pathlib import Path

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "kk", "ru"})

_TRANSLATIONS_DIR = Path(__file__).resolve().parent / "translations"
_current_locale: ContextVar[str] = ContextVar("current_locale", default=DEFAULT_LOCALE)


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    locale = value.strip().lower().replace("-", "_")
    if not locale:
        return DEFAULT_LOCALE
    language = locale.split("_", 1)[0]
    if language in SUPPORTED_LOCALES:
        return language
    return DEFAULT_LOCALE


def set_locale(locale: str) -> Token[str]:
    return _current_locale.set(normalize_locale(locale))


def reset_locale(token: Token[str]) -> None:
    _current_locale.reset(token)


def get_locale() -> str:
    return _current_locale.get()


@lru_cache
def _translations(locale: str) -> dict[str, str]:
    path = _TRANSLATIONS_DIR / f"{normalize_locale(locale)}.json"
    with path.open(encoding="utf-8") as file:
        raw = json.load(file)
    return {str(key): str(value) for key, value in raw.items()}


def translate(message_key: str) -> str:
    return _translations(get_locale()).get(message_key, message_key)


def noop(message_key: str) -> str:
    return message_key


_ = translate
N_ = noop

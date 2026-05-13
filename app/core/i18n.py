from __future__ import annotations

import gettext
from contextvars import ContextVar, Token
from functools import lru_cache
from pathlib import Path

from babel.core import negotiate_locale
from starlette.requests import Request

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = frozenset({"en", "kk", "ru"})
_SUPPORTED_LOCALE_LIST = sorted(SUPPORTED_LOCALES)

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
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


def locale_from_request(request: Request) -> str:
    accept_language = request.headers.get("accept-language")
    if not accept_language:
        return DEFAULT_LOCALE

    choices: list[tuple[float, str]] = []
    for raw_part in accept_language.split(","):
        part = raw_part.strip()
        if not part:
            continue
        language, _, raw_q = part.partition(";")
        if language.strip() == "*":
            continue
        weight = 1.0
        if raw_q.strip().startswith("q="):
            try:
                weight = float(raw_q.strip()[2:])
            except ValueError:
                weight = 0.0
        if weight <= 0:
            continue
        choices.append((weight, language.strip().replace("-", "_")))

    if not choices:
        return DEFAULT_LOCALE

    choices.sort(reverse=True)
    preferred = [locale for _, locale in choices]
    negotiated = negotiate_locale(preferred, _SUPPORTED_LOCALE_LIST, sep="_")
    return normalize_locale(negotiated)


def set_locale(locale: str) -> Token[str]:
    return _current_locale.set(normalize_locale(locale))


def reset_locale(token: Token[str]) -> None:
    _current_locale.reset(token)


def get_locale() -> str:
    return _current_locale.get()


@lru_cache
def _translation(locale: str) -> gettext.NullTranslations:
    return gettext.translation(
        "messages",
        localedir=_LOCALES_DIR,
        languages=[normalize_locale(locale)],
        fallback=True,
    )


def gettext_message(message: str) -> str:
    return _translation(get_locale()).gettext(message)


def gettext_noop(message: str) -> str:
    return message


_ = gettext_message
N_ = gettext_noop

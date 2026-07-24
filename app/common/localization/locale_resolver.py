from babel.core import negotiate_locale
from starlette.requests import Request

from app.common.localization.service import DEFAULT_LOCALE, SUPPORTED_LOCALES, normalize_locale

_SUPPORTED_LOCALE_LIST = sorted(SUPPORTED_LOCALES)


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
    negotiated = negotiate_locale(
        [locale for _, locale in choices], _SUPPORTED_LOCALE_LIST, sep="_"
    )
    return normalize_locale(negotiated)

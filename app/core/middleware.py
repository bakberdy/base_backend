import logging
from time import perf_counter
from uuid import uuid4
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from starlette.requests import Request

from app.core.logging import reset_request_id, set_request_id
from app.common.localization.locale_resolver import locale_from_request
from app.common.localization.service import SUPPORTED_LOCALES, reset_locale, set_locale
from app.common.responses.error_response import ErrorResponse

_HTTP_VALIDATION_REF = "#/components/schemas/HTTPValidationError"
logger = logging.getLogger(__name__)


def register_middlewares(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request_id_token = set_request_id(request_id)
        locale_token = set_locale(locale_from_request(request))
        started_at = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["x-request-id"] = request_id
            return response
        finally:
            duration_ms = (perf_counter() - started_at) * 1000
            logger.info(
                "request_completed method=%s path=%s status_code=%s duration_ms=%.2f client=%s",
                request.method,
                request.url.path,
                status_code,
                duration_ms,
                request.client.host if request.client else "-",
            )
            reset_locale(locale_token)
            reset_request_id(request_id_token)


def _inject_error_response_schema(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    error_schema = ErrorResponse.model_json_schema(ref_template="#/components/schemas/{model}")
    defs = error_schema.pop("$defs", None)
    if isinstance(defs, dict):
        for name, def_schema in defs.items():
            components[name] = def_schema
    components["ErrorResponse"] = error_schema


def _replace_http_validation_refs(obj: Any) -> None:
    if isinstance(obj, dict):
        if obj.get("$ref") == _HTTP_VALIDATION_REF:
            obj["$ref"] = "#/components/schemas/ErrorResponse"
        for value in obj.values():
            _replace_http_validation_refs(value)
    elif isinstance(obj, list):
        for item in obj:
            _replace_http_validation_refs(item)


def _strip_default_validation_models(schema: dict[str, Any]) -> None:
    components = schema.get("components", {}).get("schemas", {})
    if isinstance(components, dict):
        components.pop("HTTPValidationError", None)


def _normalize_422_descriptions(schema: dict[str, Any]) -> None:
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            response_422 = operation.get("responses", {}).get("422")
            if isinstance(response_422, dict) and response_422.get("description") == "Validation Error":
                response_422["description"] = "Validation failed"


def _inject_accept_language_parameter(schema: dict[str, Any]) -> None:
    supported = ", ".join(sorted(SUPPORTED_LOCALES))
    components = schema.setdefault("components", {}).setdefault("parameters", {})
    components["AcceptLanguage"] = {
        "name": "Accept-Language",
        "in": "header",
        "required": False,
        "description": (
            f"Preferred response language. Supported locales: {supported}. "
            "Examples: `kk`, `ru`, `en`, `kk-KZ`, `ru-RU`, `en-US`, "
            "`ru;q=0.9,en;q=0.8`."
        ),
        "schema": {"type": "string", "default": "en", "example": "kk"},
    }
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            parameters = operation.setdefault("parameters", [])
            if not isinstance(parameters, list):
                continue
            already_present = any(
                isinstance(param, dict)
                and param.get("name") == "Accept-Language"
                and param.get("in") == "header"
                for param in parameters
            )
            if not already_present:
                parameters.insert(0, {"$ref": "#/components/parameters/AcceptLanguage"})


def configure_openapi(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
        )
        _inject_error_response_schema(openapi_schema)
        _inject_accept_language_parameter(openapi_schema)
        _replace_http_validation_refs(openapi_schema)
        _strip_default_validation_models(openapi_schema)
        _normalize_422_descriptions(openapi_schema)
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

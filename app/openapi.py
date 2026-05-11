"""OpenAPI: replace FastAPI's default HTTPValidationError (`detail` array) with ErrorResponse."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.schemas.error import ErrorResponse

_HTTP_VALIDATION_REF = "#/components/schemas/HTTPValidationError"


def _inject_error_response_schema(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    error_schema = ErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}",
    )
    defs = error_schema.pop("$defs", None)
    if isinstance(defs, dict):
        for name, def_schema in defs.items():
            components[name] = def_schema
    components["ErrorResponse"] = error_schema


def _replace_http_validation_refs(obj: Any) -> None:
    if isinstance(obj, dict):
        ref = obj.get("$ref")
        if ref == _HTTP_VALIDATION_REF:
            obj["$ref"] = "#/components/schemas/ErrorResponse"
        for v in obj.values():
            _replace_http_validation_refs(v)
    elif isinstance(obj, list):
        for item in obj:
            _replace_http_validation_refs(item)


def _strip_legacy_validation_models(schema: dict[str, Any]) -> None:
    components = schema.get("components", {}).get("schemas", {})
    if not isinstance(components, dict):
        return
    components.pop("HTTPValidationError", None)


def _normalize_422_descriptions(schema: dict[str, Any]) -> None:
    for path_item in schema.get("paths", {}).values():
        for op in path_item.values():
            if not isinstance(op, dict):
                continue
            r422 = op.get("responses", {}).get("422")
            if isinstance(r422, dict) and r422.get("description") == "Validation Error":
                r422["description"] = "Validation failed"


def patch_openapi_schema(schema: dict[str, Any]) -> None:
    _inject_error_response_schema(schema)
    _replace_http_validation_refs(schema)
    _strip_legacy_validation_models(schema)
    _normalize_422_descriptions(schema)


def configure_openapi(app: FastAPI) -> None:
    """Swap generated OpenAPI so 422 docs describe ErrorResponse, not `{detail: [...]}`."""

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
        patch_openapi_schema(openapi_schema)
        app.openapi_schema = openapi_schema
        return openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

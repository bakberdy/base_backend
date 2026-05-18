from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Generic, TypeVar, overload

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")
RequestT = TypeVar("RequestT", bound="BaseListRequest")


class SortingMethod(str, Enum):
    ASC = "asc"
    DESC = "desc"


class BaseListRequest(BaseModel):
    page_number: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sorting_method: SortingMethod = SortingMethod.DESC
    sort_key: str = Field("created_at", min_length=1)


class PaginationParams(BaseListRequest):
    pass


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta


@overload
def build_base_list_request(request_type: None = None, **values: Any) -> BaseListRequest: ...


@overload
def build_base_list_request(request_type: type[RequestT], **values: Any) -> RequestT: ...


def build_base_list_request(
    request_type: type[RequestT] | None = None,
    **values: Any,
) -> BaseListRequest | RequestT:
    if request_type is None:
        return BaseListRequest.model_validate(values)
    return request_type.model_validate(values)


def get_pagination_params(
    page_number: int = Query(1, ge=1, alias="page_number"),
    limit: int = Query(20, ge=1, le=100, alias="limit"),
    sorting_method: SortingMethod = Query(SortingMethod.DESC, alias="sorting_method"),
    sort_key: str = Query("created_at", min_length=1, alias="sort_key"),
) -> PaginationParams:
    return build_base_list_request(
        PaginationParams,
        page_number=page_number,
        limit=limit,
        sorting_method=sorting_method,
        sort_key=sort_key,
    )


BaseListDep = Annotated[BaseListRequest, Depends(get_pagination_params)]
PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]

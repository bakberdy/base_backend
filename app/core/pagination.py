from __future__ import annotations

import math
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page_number: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


def pagination_offset(params: PaginationParams) -> int:
    return (params.page_number - 1) * params.limit


def pagination_total_pages(total_items: int, limit: int) -> int:
    if total_items <= 0:
        return 0
    return math.ceil(total_items / limit)


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


def build_pagination_meta(*, page: int, limit: int, total_items: int) -> PaginationMeta:
    total_pages = pagination_total_pages(total_items, limit)
    has_next = page < total_pages if total_pages > 0 else False
    has_previous = page > 1
    return PaginationMeta(
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )


def get_pagination_params(
    page_number: int = Query(1, ge=1, alias="page_number"),
    limit: int = Query(20, ge=1, le=100, alias="limit"),
) -> PaginationParams:
    return PaginationParams(page_number=page_number, limit=limit)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta

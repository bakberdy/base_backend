from __future__ import annotations

from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page_number: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


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


def get_pagination_params(
    page_number: int = Query(1, ge=1, alias="page_number"),
    limit: int = Query(20, ge=1, le=100, alias="limit"),
) -> PaginationParams:
    return PaginationParams(page_number=page_number, limit=limit)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]

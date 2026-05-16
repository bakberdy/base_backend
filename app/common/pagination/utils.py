import math

from app.common.pagination.schemas import PaginationMeta, PaginationParams


def pagination_offset(params: PaginationParams) -> int:
    return (params.page_number - 1) * params.limit


def pagination_total_pages(total_items: int, limit: int) -> int:
    if total_items <= 0:
        return 0
    return math.ceil(total_items / limit)


def build_pagination_meta(*, page: int, limit: int, total_items: int) -> PaginationMeta:
    total_pages = pagination_total_pages(total_items, limit)
    return PaginationMeta(
        page=page,
        limit=limit,
        total_items=total_items,
        total_pages=total_pages,
        has_next=page < total_pages if total_pages > 0 else False,
        has_previous=page > 1,
    )

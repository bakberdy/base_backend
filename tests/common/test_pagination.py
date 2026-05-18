from pydantic import ValidationError

from app.common.pagination.exceptions import InvalidSortKeyError
from app.common.pagination.schemas import (
    BaseListRequest,
    SortingMethod,
    build_base_list_request,
)
from app.common.pagination.sqlalchemy import apply_sorting
from app.common.pagination.utils import build_pagination_meta, pagination_offset


class ExampleListRequest(BaseListRequest):
    is_active: bool | None = None


class SortColumnSpy:
    def __init__(self, name: str) -> None:
        self.name = name

    def asc(self) -> str:
        return f"{self.name} asc"

    def desc(self) -> str:
        return f"{self.name} desc"


class SelectSpy:
    def __init__(self) -> None:
        self.order_by_value: str | None = None

    def order_by(self, value: str) -> "SelectSpy":
        self.order_by_value = value
        return self


def test_base_list_request_defaults_and_offset() -> None:
    request = BaseListRequest.model_validate({})

    assert request.page_number == 1
    assert request.limit == 20
    assert request.sorting_method == SortingMethod.DESC
    assert request.sort_key == "created_at"
    assert pagination_offset(request) == 0


def test_base_list_request_validates_query_input_boundaries() -> None:
    invalid_values = [
        {"page_number": 0},
        {"limit": 0},
        {"limit": 101},
        {"sorting_method": "oldest"},
        {"sort_key": ""},
    ]

    for values in invalid_values:
        try:
            BaseListRequest.model_validate(values)
        except ValidationError:
            continue
        raise AssertionError(f"Expected validation error for {values}")


def test_base_list_request_supports_extended_query_inputs() -> None:
    request = build_base_list_request(
        ExampleListRequest,
        page_number=3,
        limit=15,
        sorting_method="asc",
        sort_key="email",
        is_active=True,
    )

    assert request.page_number == 3
    assert request.limit == 15
    assert request.sorting_method == SortingMethod.ASC
    assert request.sort_key == "email"
    assert request.is_active is True
    assert pagination_offset(request) == 30


def test_pagination_meta_reports_page_boundaries() -> None:
    first_page = build_pagination_meta(page=1, limit=20, total_items=41)
    last_page = build_pagination_meta(page=3, limit=20, total_items=41)
    empty_page = build_pagination_meta(page=1, limit=20, total_items=0)

    assert first_page.total_pages == 3
    assert first_page.has_next is True
    assert first_page.has_previous is False
    assert last_page.has_next is False
    assert last_page.has_previous is True
    assert empty_page.total_pages == 0
    assert empty_page.has_next is False
    assert empty_page.has_previous is False


def test_apply_sorting_uses_requested_column_and_direction() -> None:
    asc_stmt = SelectSpy()

    asc_result = apply_sorting(
        asc_stmt,  # type: ignore[arg-type]
        sort_key="email",
        sorting_method=SortingMethod.ASC,
        sort_columns={"email": SortColumnSpy("email")},
    )
    desc_stmt = SelectSpy()
    desc_result = apply_sorting(
        desc_stmt,  # type: ignore[arg-type]
        sort_key="created_at",
        sorting_method=SortingMethod.DESC,
        sort_columns={"created_at": SortColumnSpy("created_at")},
    )

    assert asc_result is asc_stmt
    assert asc_stmt.order_by_value == "email asc"
    assert desc_result is desc_stmt
    assert desc_stmt.order_by_value == "created_at desc"


def test_apply_sorting_rejects_unknown_sort_key() -> None:
    try:
        apply_sorting(
            SelectSpy(),  # type: ignore[arg-type]
            sort_key="missing",
            sorting_method=SortingMethod.DESC,
            sort_columns={"created_at": SortColumnSpy("created_at")},
        )
    except InvalidSortKeyError as exc:
        assert exc.details == {
            "sort_key": "missing",
            "allowed_sort_keys": ["created_at"],
        }
        return
    raise AssertionError("Expected InvalidSortKeyError")

from collections.abc import Mapping
from typing import Any

from sqlalchemy.sql import Select

from app.common.pagination.exceptions import InvalidSortKeyError
from app.common.pagination.schemas import SortingMethod


SortColumns = Mapping[str, Any]


def model_sort_columns(model: type[Any]) -> dict[str, Any]:
    return {column.name: getattr(model, column.name) for column in model.__table__.columns}


def apply_sorting(
    stmt: Select[Any],
    *,
    sort_key: str,
    sorting_method: SortingMethod,
    sort_columns: SortColumns,
) -> Select[Any]:
    column = sort_columns.get(sort_key)
    if column is None:
        raise InvalidSortKeyError(sort_key, sorted(sort_columns))
    order_by = column.asc() if sorting_method == SortingMethod.ASC else column.desc()
    return stmt.order_by(order_by)

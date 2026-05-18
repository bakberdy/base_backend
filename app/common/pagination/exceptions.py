from app.common.exceptions.base import ApplicationError


class InvalidSortKeyError(ApplicationError):
    def __init__(self, sort_key: str, allowed_sort_keys: list[str]) -> None:
        super().__init__(
            "INVALID_SORT_KEY",
            {
                "sort_key": sort_key,
                "allowed_sort_keys": allowed_sort_keys,
            },
        )

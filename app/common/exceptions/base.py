from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ApplicationError(Exception):
    code: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        super().__init__(self.code)

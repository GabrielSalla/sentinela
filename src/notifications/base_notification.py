from dataclasses import dataclass
from functools import partial
from typing import Coroutine

from dataclass_type_validator import dataclass_validate


@dataclass_validate(strict=True)
@dataclass
class BaseNotification:
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[Coroutine | partial[Coroutine]]]]:
        return []  # pragma: no cover

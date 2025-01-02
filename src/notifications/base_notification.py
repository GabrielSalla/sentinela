from functools import partial
from typing import Coroutine, Protocol, runtime_checkable


@runtime_checkable
class BaseNotification(Protocol):
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[Coroutine | partial[Coroutine]]]]: ...

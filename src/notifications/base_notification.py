from typing import Any, Callable, Coroutine, Protocol, runtime_checkable

type async_function = Callable[[dict[str, Any]], Coroutine[Any, Any, Any]]


@runtime_checkable
class BaseNotification(Protocol):
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[async_function]]]: ...

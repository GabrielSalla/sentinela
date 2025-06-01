from typing import Protocol, runtime_checkable

from data_models.monitor_options import reaction_function_type


@runtime_checkable
class BaseNotification(Protocol):  # pragma: no cover
    min_priority_to_send: int = 5

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]: ...

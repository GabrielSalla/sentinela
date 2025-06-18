from typing import Any, Protocol, runtime_checkable

from data_models.monitor_options import reaction_function_type
from models.utils.priority import AlertPriority


@runtime_checkable
class BaseNotification(Protocol):  # pragma: no cover
    min_priority_to_send: AlertPriority = AlertPriority.informational

    @classmethod
    def create(
        cls: type["BaseNotification"],
        name: str,
        issues_fields: list[str],
        params: dict[str, Any],
    ) -> "BaseNotification": ...

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]: ...

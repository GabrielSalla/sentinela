from typing import Protocol, runtime_checkable

from data_models.monitor_options import reaction_function_type
from models.utils.priority import AlertPriority


@runtime_checkable
class BaseNotification(Protocol):  # pragma: no cover
    min_priority_to_send: AlertPriority = AlertPriority.informational

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]: ...

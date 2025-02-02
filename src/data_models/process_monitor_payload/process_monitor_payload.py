from typing import Literal

from pydantic.dataclasses import dataclass


@dataclass
class ProcessMonitorPayload:
    monitor_id: int
    tasks: list[Literal["search", "update"]]

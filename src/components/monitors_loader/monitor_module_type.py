from pathlib import Path
from typing import Protocol

from data_models.monitor_options import AlertOptions, IssueOptions, MonitorOptions, ReactionOptions
from notifications import BaseNotification


class MonitorModule(Protocol):  # pragma: no cover
    """Class that represents a base monitor module structure"""

    SENTINELA_MONITOR_ID: int
    SENTINELA_MONITOR_NAME: str
    SENTINELA_MONITOR_PATH: Path

    monitor_options: MonitorOptions
    issue_options: IssueOptions
    alert_options: AlertOptions

    @staticmethod
    async def search() -> list[dict] | None: ...

    @staticmethod
    async def update(issues_data: list[dict]) -> list[dict] | None: ...

    @staticmethod
    def is_solved(issue_data: dict) -> bool: ...

    reaction_options: ReactionOptions

    notification_options: list[BaseNotification]

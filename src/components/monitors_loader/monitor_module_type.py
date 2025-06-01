from pathlib import Path
from typing import Protocol, TypedDict

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

    class IssueDataType(TypedDict): ...

    @staticmethod
    async def search() -> list[IssueDataType] | None: ...

    @staticmethod
    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...

    @staticmethod
    def is_solved(issue_data: IssueDataType) -> bool: ...

    reaction_options: ReactionOptions

    notification_options: list[BaseNotification]

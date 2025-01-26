from typing import Protocol, TypedDict

from notifications import BaseNotification
from options import AlertOptions, IssueOptions, MonitorOptions, ReactionOptions


class MonitorModule(Protocol):
    """Class that represents a base monitor module structure to have a better code completion"""

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

from types import ModuleType
from typing import TypedDict

from notifications import BaseNotification
from options import AlertOptions, IssueOptions, MonitorOptions, ReactionOptions


class MonitorModule(ModuleType):  # pragma: no cover
    """Class that represents a base monitor module structure to have a better code completion"""
    monitor_options: MonitorOptions
    issue_options: IssueOptions
    alert_options: AlertOptions

    class IssueDataType(TypedDict):
        pass

    @staticmethod
    async def search() -> list[IssueDataType] | None: ...

    @staticmethod
    async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None: ...

    @staticmethod
    def is_solved(issue_data: IssueDataType) -> bool:
        return False

    reaction_options: ReactionOptions

    notification_options: list[BaseNotification]

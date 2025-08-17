const MONITOR_TEMPLATE = `from typing import TypedDict

from monitor_utils import IssueOptions, MonitorOptions
from notifications.internal_monitor_notification import internal_monitor_notification

monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="",
    solvable=True,
)

alert_options = None


class IssueDataType(TypedDict):
    pass


async def search() -> list[IssueDataType] | None:
    return []


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    return False


notification_options = []
`;

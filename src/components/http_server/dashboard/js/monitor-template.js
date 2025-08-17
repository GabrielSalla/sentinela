const MONITOR_TEMPLATE = `from typing import TypedDict

from monitor_utils import IssueOptions, MonitorOptions
from notifications.internal_monitor_notification import internal_monitor_notification

# Monitor configuration
monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

# Issue configuration
issue_options = IssueOptions(
    model_id_key="",
    solvable=True,
)

# Alert configuration
alert_options = None


# Define your issue data structure
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

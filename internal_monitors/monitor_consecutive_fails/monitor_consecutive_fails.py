"""Monitor with high consecutive fails
Objective: check for Monitors with high consecutive fails.
"""

from typing import TypedDict, cast

from databases import query_application
from monitor_utils import (
    AlertOptions,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ValueRule,
    read_file,
)
from notifications.internal_monitor_notification import internal_monitor_notification


class IssueDataType(TypedDict):
    monitor_id: int
    monitor_name: str
    monitor_enabled: bool
    failed_count: int


monitor_options = MonitorOptions(
    update_cron="*/2 * * * *",
    search_cron="*/5 * * * *",
)

issue_options = IssueOptions(
    model_id_key="monitor_id",
    solvable=True,
)

alert_options = AlertOptions(
    rule=ValueRule(
        value_key="failed_count",
        operation="greater_than",
        priority_levels=PriorityLevels(
            moderate=3,
            high=5,
            critical=10,
        ),
    )
)


async def search() -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    return cast(list[IssueDataType], await query_application(sql))


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("update_query.sql")
    monitors_ids = [issue_data["monitor_id"] for issue_data in issues_data]

    return cast(list[IssueDataType], await query_application(sql, monitors_ids))


def is_solved(issue_data: IssueDataType) -> bool:
    monitor_enabled = issue_data["monitor_enabled"]
    failed_count = issue_data["failed_count"]
    return not monitor_enabled or failed_count == 0


notification_options = internal_monitor_notification(
    name="Monitor with high consecutive fails",
    issues_fields=["monitor_id", "monitor_name", "failed_count"],
)

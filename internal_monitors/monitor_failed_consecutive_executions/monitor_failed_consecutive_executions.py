"""Monitor failed consecutive executions
Objective: check for Monitors that failed executing at least 5 consecutive times.
"""

from datetime import datetime
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

ERROR_THRESHOLD = 5


class IssueDataType(TypedDict):
    monitor_id: int
    monitor_name: str
    monitor_enabled: bool
    consecutive_errors: int
    last_success: datetime | None


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
        value_key="consecutive_errors",
        operation="greater_than",
        priority_levels=PriorityLevels(
            moderate=ERROR_THRESHOLD - 1,
            high=ERROR_THRESHOLD * 2 - 1,
            critical=ERROR_THRESHOLD * 3 - 1,
        ),
    )
)


async def search() -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    monitors_metrics = cast(list[IssueDataType], await query_application(sql))

    return [
        monitor_metric
        for monitor_metric in monitors_metrics
        if monitor_metric["consecutive_errors"] >= ERROR_THRESHOLD
        and monitor_metric["monitor_enabled"]
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    monitors_metrics = cast(list[IssueDataType], await query_application(sql))

    active_issues_monitor_ids = {issue_data["monitor_id"] for issue_data in issues_data}

    return [
        monitor_metric
        for monitor_metric in monitors_metrics
        if monitor_metric["monitor_id"] in active_issues_monitor_ids
    ]


def is_solved(issue_data: IssueDataType) -> bool:
    consecutive_errors = issue_data["consecutive_errors"]
    return consecutive_errors < ERROR_THRESHOLD or not issue_data["monitor_enabled"]


notification_options = internal_monitor_notification(
    name="Monitor failed consecutive executions",
    issues_fields=["monitor_id", "monitor_name", "consecutive_errors", "last_success"],
)

from typing import Any, TypedDict, cast

from monitor_utils import (
    AlertOptions,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ReactionOptions,
    ValueRule,
    read_file,
)

from src.configs import configs
from src.databases import query_application
from src.models import Monitor

monitor_options = MonitorOptions(
    update_cron="* * * * *",
    search_cron="*/5 * * * *",
)

issue_options = IssueOptions(
    model_id_key="monitor_id",
    solvable=True,
)

alert_options = AlertOptions(
    rule=ValueRule(
        value_key="seconds_queued",
        operation="greater_than",
        priority_levels=PriorityLevels(
            moderate=12*configs.executor_monitor_timeout,
            high=15*configs.executor_monitor_timeout,
            critical=20*configs.executor_monitor_timeout,
        )
    )
)


class IssueDataType(TypedDict):
    monitor_id: int
    monitor_queued: bool
    seconds_queued: int


async def search() -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    time_tolerance = 5 * configs.executor_monitor_timeout
    monitors_list = cast(
        list[IssueDataType],
        await query_application(sql, time_tolerance)
    )

    return monitors_list


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("update_query.sql")

    monitors_ids = [issue_data["monitor_id"] for issue_data in issues_data]
    monitors_list = cast(
        list[IssueDataType],
        await query_application(sql, monitors_ids)
    )

    return monitors_list


def is_solved(issue_data: IssueDataType) -> bool:
    """Issue is solved when the monitor is not queued or it's been queued in the last 2 minutes"""
    issue_seconds_queued = issue_data["seconds_queued"]
    monitor_queued = issue_data["monitor_queued"]
    return not monitor_queued or issue_seconds_queued <= 120


# Reactions

async def reaction_issue_created(event_payload: dict[str, Any]):
    """Fix the monitor by setting it's 'queued' value to 'false'"""
    issue_data = event_payload["event_data"]
    monitor = await Monitor.get_by_id(issue_data["data"]["monitor_id"])
    if monitor:
        monitor.set_queued(False)
        await monitor.save()


reaction_options = ReactionOptions(
    issue_created=[reaction_issue_created],
    issue_updated_not_solved=[reaction_issue_created],
)

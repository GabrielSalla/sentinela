"""Monitor with high active issues count
Objective: check for Monitors with high active issues count to prevent the application from being
affected from a high resource usage.
"""

import os
from typing import TypedDict, cast

from databases import query_application
from monitor_utils import (
    AlertOptions,
    AlertPriority,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ValueRule,
    read_file,
)
from plugins.slack import SlackNotification

TRIGGER_THRESHOLD = 500

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
        value_key="active_issues_count",
        operation="greater_than",
        priority_levels=PriorityLevels(
            moderate=TRIGGER_THRESHOLD,
            high=2 * TRIGGER_THRESHOLD,
            critical=3 * TRIGGER_THRESHOLD,
        ),
    )
)


class IssueDataType(TypedDict):
    monitor_id: int
    monitor_name: str
    active_issues_count: int


async def search() -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    return cast(list[IssueDataType], await query_application(sql, TRIGGER_THRESHOLD))


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    return cast(list[IssueDataType], await query_application(sql, TRIGGER_THRESHOLD))


def is_solved(issue_data: IssueDataType) -> bool:
    active_issues_count = issue_data["active_issues_count"]
    return active_issues_count < TRIGGER_THRESHOLD / 2


notification_options = [
    SlackNotification(
        channel=os.environ["SLACK_MAIN_CHANNEL"],
        title="Monitor with high active issues count",
        issues_fields=["monitor_id", "monitor_name", "active_issues_count"],
        mention=os.environ["SLACK_MAIN_MENTION"],
        min_priority_to_send=AlertPriority.low,
        min_priority_to_mention=AlertPriority.moderate,
    )
]

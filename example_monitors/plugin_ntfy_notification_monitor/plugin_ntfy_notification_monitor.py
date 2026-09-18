"""
ntfy Notification Monitor

This monitor demonstrates how to configure ntfy notifications.
A single issue's error rate climbs every cycle, escalating the alert priority up to
critical (P1). Once the error rate reaches the top, the issue is solved in the next
cycle, solving the alert, and the cycle starts over.
"""

import random
from typing import TypedDict

from monitor_utils import AlertOptions, IssueOptions, MonitorOptions, PriorityLevels, ValueRule
from plugins.ntfy.notifications import NtfyNotification


class IssueDataType(TypedDict):
    id: str
    error_rate: float


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

alert_options = AlertOptions(
    rule=ValueRule(
        value_key="error_rate",
        operation="greater_than",
        priority_levels=PriorityLevels(
            low=10,
            moderate=25,
            high=50,
            critical=75,
        ),
    )
)


async def search() -> list[IssueDataType] | None:
    return [{"id": "sample issue", "error_rate": 0.0}]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    issue_data = issues_data[0]
    issue_data["error_rate"] = min(100.0, issue_data["error_rate"] + random.uniform(15, 25))
    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    return issue_data["error_rate"] >= 95


# ntfy notifications for this monitor
# IMPORTANT: change the topic below to your own topic, otherwise your alerts
# will be published to a public topic shared with other users.
notification_options = [
    NtfyNotification(
        topic="sentinela-example",
        title="ntfy Notification Monitor",
    )
]

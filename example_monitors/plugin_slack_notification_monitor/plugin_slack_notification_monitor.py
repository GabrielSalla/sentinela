"""
Slack Notification Monitor

This monitor demonstrates how to configure Slack notifications.
"""

import os
import random
import time
from typing import TypedDict

from monitor_utils import AlertOptions, CountRule, IssueOptions, MonitorOptions, PriorityLevels
from plugins.slack.notifications import SlackNotification


class IssueDataType(TypedDict):
    id: int
    severity: int


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=0,
            moderate=5,
            high=10,
            critical=15,
        )
    )
)


async def search() -> list[IssueDataType] | None:
    return [
        {
            "id": random.randrange(1, 100000),
            "severity": random.randrange(1, 10),
        }
        for _ in range(5)
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    is_solving_window = (time.time() // 60) % 5 == 0

    for issue_data in issues_data:
        if is_solving_window and random.random() < 0.9:
            issue_data["severity"] = 1
        else:
            issue_data["severity"] = random.randrange(1, 10)

    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    return issue_data["severity"] == 1


# Slack notifications for this monitor
notification_options = [
    SlackNotification(
        channel=os.environ.get("SLACK_MAIN_CHANNEL", ""),
        title="Slack Notification Monitor",
        issues_fields=["id", "severity"],
        mention=os.environ.get("SLACK_MAIN_MENTION"),
    )
]

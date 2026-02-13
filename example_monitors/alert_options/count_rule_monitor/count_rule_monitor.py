"""
Count Rule Monitor

This monitor demonstrates the CountRule.
The alert priority is determined by the number of active issues.
More active issues trigger higher priority alerts.
"""

import random
import time
from typing import TypedDict

from monitor_utils import AlertOptions, CountRule, IssueOptions, MonitorOptions, PriorityLevels


class IssueDataType(TypedDict):
    id: int
    value: int


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

# CountRule: Priority is based on the number of active issues
# An alert's priority increases as more issues are linked to it
alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=0,  # more than 0 active issues
            moderate=5,  # more than 5 active issues
            high=10,  # more than 10 active issues
            critical=15,  # more than 15 active issues
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Return 5 issues to demonstrate how the count of active issues affects
    # the alert priority level
    return [
        {
            "id": random.randrange(1, 100000),
            "value": random.randrange(1, 10),
        }
        for _ in range(5)
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Every 5 minutes, there's a 90% chance of issues being solved
    # This demonstrates how the count of active issues fluctuates over time
    is_solving_window = (time.time() // 60) % 5 == 0

    for issue_data in issues_data:
        if is_solving_window and random.random() < 0.9:
            issue_data["value"] = 1
        else:
            issue_data["value"] = random.randrange(1, 10)

    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # Issue is solved when value equals to 1
    return issue_data["value"] == 1

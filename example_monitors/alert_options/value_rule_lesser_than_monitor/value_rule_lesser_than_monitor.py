"""
Value Rule Less Than Monitor

This monitor demonstrates the ValueRule with the "less_than" operation.
The alert priority is determined by a specific numerical value from the issue data.
A single issue's success rate oscillates from 100 to 0 and back, triggering different
priority levels as the value changes.
"""

import random
from typing import TypedDict

from monitor_utils import AlertOptions, IssueOptions, MonitorOptions, PriorityLevels, ValueRule


class IssueDataType(TypedDict):
    id: str
    success_rate: float
    trend: str


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

# ValueRule: Priority is based on a value from the issue data
# The alert's priority is determined by comparing the 'success_rate' field
# against the priority level thresholds using the 'less_than' operation
alert_options = AlertOptions(
    rule=ValueRule(
        value_key="success_rate",
        operation="lesser_than",
        priority_levels=PriorityLevels(
            low=90,  # success_rate < 90%
            moderate=75,  # success_rate < 75%
            high=50,  # success_rate < 50%
            critical=25,  # success_rate < 25%
        ),
    )
)


async def search() -> list[IssueDataType] | None:
    # Return a single issue with success rate starting at 100 and trend falling
    return [
        {
            "id": "sample issue",
            "success_rate": 100.0,
            "trend": "falling",
        }
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Update the single issue's success rate by a random value between 10 and 25
    # Use the trend stored in the issue to determine direction
    # Trend flips when reaching 0 or 100
    issue_data = issues_data[0]

    direction = 1 if issue_data["trend"] == "rising" else -1
    change = random.uniform(10, 25) * direction
    new_success_rate = issue_data["success_rate"] + change

    # Flip trend and clamp to boundaries
    if new_success_rate >= 95:
        if new_success_rate > 100:
            new_success_rate = 100
        new_trend = "falling"
    elif new_success_rate <= 5:
        if new_success_rate < 0:
            new_success_rate = 0
        new_trend = "rising"
    else:
        new_trend = issue_data["trend"]

    issue_data["success_rate"] = new_success_rate
    issue_data["trend"] = new_trend
    return [issue_data]


def is_solved(issue_data: IssueDataType) -> bool:
    # This issue never solves
    return False

"""
Value Rule Greater Than Monitor

This monitor demonstrates the ValueRule with the "greater_than" operation.
The alert priority is determined by a specific numerical value from the issue data.
A single issue's error rate oscillates from 0 to 100 and back, triggering different
priority levels as the value changes.
"""

import random
from typing import TypedDict

from monitor_utils import AlertOptions, IssueOptions, MonitorOptions, PriorityLevels, ValueRule


class IssueDataType(TypedDict):
    id: str
    error_rate: float
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
# The alert's priority is determined by comparing the 'error_rate' field
# against the priority level thresholds using the 'greater_than' operation
alert_options = AlertOptions(
    rule=ValueRule(
        value_key="error_rate",
        operation="greater_than",
        priority_levels=PriorityLevels(
            low=10,  # error_rate > 10%
            moderate=25,  # error_rate > 25%
            high=50,  # error_rate > 50%
            critical=75,  # error_rate > 75%
        ),
    )
)


async def search() -> list[IssueDataType] | None:
    # Return a single issue with error rate starting at 0 and trend rising
    return [
        {
            "id": "sample issue",
            "error_rate": 0.0,
            "trend": "rising",
        }
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Update the single issue's error rate by a random value between 10 and 25
    # Use the trend stored in the issue to determine direction
    # Trend flips when reaching 0 or 100
    issue_data = issues_data[0]

    direction = 1 if issue_data["trend"] == "rising" else -1
    change = random.uniform(10, 25) * direction
    new_error_rate = issue_data["error_rate"] + change

    # Flip trend and clamp to boundaries
    if new_error_rate >= 95:
        if new_error_rate > 100:
            new_error_rate = 100
        new_trend = "falling"
    elif new_error_rate <= 5:
        if new_error_rate < 0:
            new_error_rate = 0
        new_trend = "rising"
    else:
        new_trend = issue_data["trend"]

    issue_data["error_rate"] = new_error_rate
    issue_data["trend"] = new_trend
    return [issue_data]


def is_solved(issue_data: IssueDataType) -> bool:
    # This issue never solves
    return False

"""
Age Rule Monitor

This monitor demonstrates the AgeRule.
The alert priority is determined by the age of the oldest active issue.
Issues age over time, and older issues trigger higher priority alerts.
"""

import time
from datetime import datetime
from typing import TypedDict

from monitor_utils import AgeRule, AlertOptions, IssueOptions, MonitorOptions, PriorityLevels


class IssueDataType(TypedDict):
    id: int
    created_at: str


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

# AgeRule: Priority is based on issue age in seconds
# An alert's priority is determined by the age of the oldest active issue
alert_options = AlertOptions(
    rule=AgeRule(
        priority_levels=PriorityLevels(
            low=0,  # 0 seconds
            moderate=60,  # 1 minute
            high=120,  # 2 minutes
            critical=180,  # 3 minutes
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Every 5 minutes, a new ID is generated, creating a new issue
    # This allows observing the alert priority increasing as the issue ages,
    # with a new issue appearing every 5 minutes
    issue_id = int(time.time() // 300)
    return [
        {
            "id": issue_id,
            "created_at": datetime.now().isoformat(),
        }
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Keep the original issue data
    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # Issue is solved after 5 minutes have passed since its creation
    # This demonstrates automatic resolution based on issue age
    created_at = datetime.fromisoformat(issue_data["created_at"])
    age_seconds = (datetime.now() - created_at).total_seconds()
    return age_seconds >= 290  # The issue will be solved just before completing 5 minutes

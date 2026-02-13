"""
Non-Solvable Issues Monitor

This monitor demonstrates configuring issues as non-solvable.
Non-solvable issues require manual intervention to be solved and cannot be
automatically resolved by the monitor logic. This is useful for final states
that would result in issues never being resolved.
"""

import random
import string
from typing import TypedDict, cast

from monitor_utils import (
    AlertOptions,
    CountRule,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
)


class IssueDataType(TypedDict):
    id: int
    username: str
    deactivated: bool


monitor_options = MonitorOptions(
    search_cron="*/5 * * * *",
    update_cron="*/5 * * * *",
)

# Non-solvable issues: set solvable=False and unique=True
# unique=True ensures only one issue per deactivated user If the same user
# appears in subsequent searches the issue won't be created again because it
# was already created before
issue_options = IssueOptions(
    model_id_key="id",
    solvable=False,
    unique=True,
)

alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=1,
            moderate=3,
            high=5,
            critical=8,
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Simulate finding deactivated users (a permanent state)
    # These users won't be automatically "solved" by monitor logic—
    # they require the user to manually solve the alert and its issues
    # through the dashboard or one of the notifications, when available
    return cast(
        list[IssueDataType],
        [
            {
                "id": random.randrange(1, 100000),
                "username": "".join(random.choices(string.ascii_lowercase, k=16)),
                "deactivated": True,
            }
        ],
    )


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Keep the issue data unchanged
    # A deactivated user remains deactivated unless manually reactivated
    return issues_data

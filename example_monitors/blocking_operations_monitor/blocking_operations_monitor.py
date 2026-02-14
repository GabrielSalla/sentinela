"""
Blocking Operations Monitor

This monitor demonstrates how to handle blocking operations in search and
update functions without affecting the entire application.
"""

import asyncio
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

alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=0,
        )
    )
)


def find() -> int:
    # Simulates a long blocking operation
    time.sleep(2)
    return int(time.time())


async def search() -> list[IssueDataType] | None:
    # Get the value from a long blocking operation in a non-blocking way
    # using 'asyncio.to_thread'
    value = await asyncio.to_thread(find)
    return [
        {
            "id": 1,
            "value": value,
        }
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Get the value from a long blocking operation in a non-blocking way
    # using 'asyncio.to_thread'
    value = await asyncio.to_thread(find)
    issues_data[0]["value"] = value
    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # Issue will never be solved
    return False

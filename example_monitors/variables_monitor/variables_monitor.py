"""
Variables Monitor

This monitor demonstrates the variables feature for maintaining monitor-level state.
Variables store information about the monitor's execution, not about individual issues.
This example uses a variable to bookmark the last timestamp processed, avoiding
reprocessing the same events and making searches more efficient.
"""

import random
import time
from typing import TypedDict

from monitor_utils import (
    AlertOptions,
    CountRule,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    variables,
)


class IssueDataType(TypedDict):
    id: int
    event_timestamp: int
    error_message: str


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
            moderate=2,
            high=4,
            critical=6,
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Get the last timestamp we processed from variables
    # This allows the monitor to only process new events since the last run
    last_timestamp = await variables.get_variable("last_processed_timestamp")

    # Simulate fetching events from a data source (database, API, log file, etc)
    # In real scenarios, you'd filter events where timestamp > last_timestamp
    events: list[IssueDataType] = []
    now = int(time.time())

    # Generate random events with timestamps in the last 5 minutes
    # In production, 'event_time' would come from the data source
    # Here we forge it with random values to keep the example simple
    for i in range(random.randrange(0, 6)):
        event_time = now - random.randrange(0, 300)

        # Only include events newer than the last processed timestamp
        if last_timestamp is None or event_time > int(last_timestamp):
            events.append(
                {
                    "id": random.randrange(1, 100000),
                    "event_timestamp": event_time,
                    "error_message": f"Error event {i}",
                }
            )

    # Update the monitor bookmark to the current time
    await variables.set_variable("last_processed_timestamp", str(now))

    return events


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Keep the original event data unchanged
    # Variables don't change issue data; issue updates come from the data source
    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # Every 10 minutes, there's a 90% chance of issues being solved
    is_solving_window = (time.time() // 60) % 10 == 0
    return is_solving_window and random.random() < 0.9

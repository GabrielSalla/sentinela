"""
Query Monitor

This monitor demonstrates using the query function to fetch data from a database.
The monitor executes a simple query to illustrate the pattern for connecting to
databases. In a real-world scenario, you would replace the example query with
one that retrieves meaningful data for your monitoring needs.
"""

from typing import TypedDict

from monitor_utils import (
    AlertOptions,
    CountRule,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    query,
)


class IssueDataType(TypedDict):
    id: str
    current_timestamp: str


monitor_options = MonitorOptions(
    search_cron="* * * * *",
    update_cron="* * * * *",
)

issue_options = IssueOptions(
    model_id_key="id",
    solvable=False,
)

alert_options = AlertOptions(
    rule=CountRule(
        priority_levels=PriorityLevels(
            low=0,
            moderate=1,
            high=2,
            critical=3,
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Execute a simple query on the 'local' database to demonstrate
    # the query function usage In a real monitor, replace this with
    # a meaningful query that retrieves data relevant to your use case
    result = await query(
        name="local",
        sql="select current_timestamp;",
    )
    if not result:
        return None
    current_timestamp = result[0]["current_timestamp"]

    if result and len(result) > 0:
        return [
            {
                "id": "database_connection_check",
                "current_timestamp": current_timestamp,
            }
        ]

    return None


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Update each issue with the current database timestamp
    result = await query(
        name="local",
        sql="SELECT current_timestamp;",
    )
    if not result:
        return None
    current_timestamp = result[0]["current_timestamp"]

    for issue in issues_data:
        issue["current_timestamp"] = current_timestamp

    return issues_data

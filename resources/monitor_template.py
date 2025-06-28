"""
Monitor template
Read the documentation to learn how to configure each field.
"""

from typing import TypedDict

from monitor_utils import AlertOptions, CountRule, IssueOptions, MonitorOptions, PriorityLevels


# Define the data structure of the issues
class IssueDataType(TypedDict):
    pass


monitor_options = MonitorOptions(
    search_cron="*/15 * * * *",
    update_cron="*/5 * * * *",
)

# Define the behavior expected for the issues
issue_options = IssueOptions(
    model_id_key="id",
    solvable=True,
)

# Define the alert triggering options
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
    """Logic to search for the issues"""
    pass


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    """Logic to update the issues data"""
    pass


def is_solved(issue_data: IssueDataType) -> bool:
    """Logic to determine if the issue is solved, based on its data"""
    return True


# Notification configurations
notification_options = []

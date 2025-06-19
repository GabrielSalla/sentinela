import random
from typing import TypedDict

from monitor_utils import AlertOptions, CountRule, IssueOptions, MonitorOptions, PriorityLevels
from notifications.internal_monitor_notification import internal_monitor_notification

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
            moderate=10,
            high=20,
            critical=30,
        )
    )
)


class IssueDataType(TypedDict):
    id: int
    value: int


async def search() -> list[IssueDataType] | None:
    # Return 5 issues data with a random 'id' and a random 'value' between 1
    # and 10
    # As an issue is considered 'solved' (check the 'is_solved' function) if
    # their 'value' equals to 1, only issues data where the 'value' is greater
    # than 1 will be created
    # The issues created will have their 'model_id' equal to the 'id' returned
    # by this function (as defined in the 'issue_options' settings)
    return [
        {
            "id": random.randrange(1, 100000),
            "value": random.randrange(1, 10),
        }
        for _ in range(5)
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Each existing issue will have their 'value' field updated to a random
    # value between 1 and 10
    for issue_data in issues_data:
        issue_data["value"] = random.randrange(1, 10)

    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # At the issues check stage, each issue data will be validated against this
    # rule and, if true, will be considered as solved
    return issue_data["value"] == 1


notification_options = internal_monitor_notification(
    name="Test monitor", issues_fields=["id", "value"]
)

import os
import random
from typing import TypedDict

from monitor_utils import AlertOptions, CountRule, IssueOptions, MonitorOptions, PriorityLevels
from plugins.slack import SlackNotification

monitor_options = MonitorOptions(
    update_cron="* * * * *",
    search_cron="* * * * *",
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
    return [
        {"id": random.randrange(1, 100000), "value": random.randrange(1, 10)}
        for _ in range(5)
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    for issue_data in issues_data:
        issue_data["value"] = random.randrange(1, 10)

    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    return issue_data["value"] == 1


notification_options = [
    SlackNotification(
        channel=os.environ["SAMPLE_SLACK_CHANNEL"],
        title="Test module",
        issues_fields=["id", "value"],
        mention=os.environ["SAMPLE_SLACK_MENTION"],
    )
]

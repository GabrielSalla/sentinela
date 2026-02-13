"""
Reactions Monitor

This monitor demonstrates how to configure reactions.
Reactions are async callbacks triggered by specific events during monitor execution.
The reaction functions here do nothing, but their comments explain when they run
and what data is available.
"""

import json
import logging
import random
from typing import TypedDict

from monitor_utils import (
    AlertOptions,
    CountRule,
    EventPayload,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ReactionOptions,
)


class IssueDataType(TypedDict):
    id: int
    value: int


logger = logging.getLogger("reactions_monitor")


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
            low=1,
            moderate=3,
            high=5,
            critical=8,
        )
    )
)


async def search() -> list[IssueDataType] | None:
    # Create a small, random set of issues to trigger reactions
    count = random.randrange(0, 4)
    return [
        {
            "id": random.randrange(1, 100000),
            "value": random.randrange(1, 10),
        }
        for _ in range(count)
    ]


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    # Update each issue with a new random value
    for issue_data in issues_data:
        issue_data["value"] = random.randrange(1, 10)

    return issues_data


def is_solved(issue_data: IssueDataType) -> bool:
    # Issues are solved when value reaches 1
    return issue_data["value"] == 1


async def reaction_issue_created(event_payload: EventPayload) -> None:
    # Called when an issue is created
    # Example use: post a message or call an API
    # This log message will appear in light blue
    json_payload = json.dumps(event_payload.to_dict())
    logger.info(f"\033[94mReaction: issue_created. Event payload: {json_payload}\033[0m")


async def reaction_issue_solved(event_payload: EventPayload) -> None:
    # Called when an issue is solved
    # Example use: notify a team or close related tickets
    # This log message will appear in light blue
    json_payload = json.dumps(event_payload.to_dict())
    logger.info(f"\033[94mReaction: issue_solved. Event payload: {json_payload}\033[0m")


async def reaction_alert_priority_increased(event_payload: EventPayload) -> None:
    # Called when an alert priority increases
    # Example use: page on-call or escalate a notification channel
    # This log message will appear in light blue
    json_payload = json.dumps(event_payload.to_dict())
    logger.info(f"\033[94mReaction: alert_priority_increased. Event payload: {json_payload}\033[0m")


reaction_options = ReactionOptions(
    issue_created=[reaction_issue_created],
    issue_solved=[reaction_issue_solved],
    alert_priority_increased=[reaction_alert_priority_increased],
)

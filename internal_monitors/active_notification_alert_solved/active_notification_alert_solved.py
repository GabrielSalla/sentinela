"""Active notification for solved alert
Objective: check for active Notifications where the associated alert has already been solved.
The Monitor tries to automatically close the issues by closing the detected Notifications. If a
Notification is not closed successfully, the Monitor will trigger a Slack notification.
"""

import os
from typing import TypedDict, cast

from databases import query_application
from models import Notification, NotificationStatus
from monitor_utils import (
    AgeRule,
    AlertOptions,
    AlertPriority,
    EventPayload,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ReactionOptions,
    read_file,
)
from plugins.slack import SlackNotification

monitor_options = MonitorOptions(
    update_cron="*/5 * * * *",
    search_cron="*/30 * * * *",
)

issue_options = IssueOptions(
    model_id_key="notification_id",
    solvable=True,
)

alert_options = AlertOptions(
    rule=AgeRule(
        priority_levels=PriorityLevels(
            low=300,
            moderate=360,
            high=420,
            critical=480,
        )
    )
)


class IssueDataType(TypedDict):
    notification_id: int
    notification_status: str


async def search() -> list[IssueDataType] | None:
    sql = read_file("search_query.sql")

    return cast(list[IssueDataType], await query_application(sql))


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("update_query.sql")

    notifications_ids = [issue_data["notification_id"] for issue_data in issues_data]
    return cast(list[IssueDataType], await query_application(sql, notifications_ids))


def is_solved(issue_data: IssueDataType) -> bool:
    notification_status = issue_data["notification_status"]
    return notification_status == NotificationStatus.closed.value


# Reactions


async def close_notification(event_payload: EventPayload) -> None:
    """Fix the notification by closing it"""
    issue_object = event_payload.event_data
    notification = await Notification.get_by_id(issue_object["data"]["notification_id"])
    if notification:
        await notification.close()


reaction_options = ReactionOptions(
    issue_created=[close_notification],
    issue_updated_not_solved=[close_notification],
)

notification_options = [
    SlackNotification(
        channel=os.environ["SLACK_MAIN_CHANNEL"],
        title="Active notification for solved alert",
        issues_fields=["notification_id", "notification_status"],
        mention=os.environ["SLACK_MAIN_MENTION"],
        min_priority_to_send=AlertPriority.low,
        min_priority_to_mention=AlertPriority.moderate,
    )
]

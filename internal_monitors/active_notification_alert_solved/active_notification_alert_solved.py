from typing import Any, TypedDict, cast

from databases import query_application
from models import Notification, NotificationStatus
from monitor_utils import (
    AgeRule,
    AlertOptions,
    IssueOptions,
    MonitorOptions,
    PriorityLevels,
    ReactionOptions,
    read_file,
)

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

    notifications_list = cast(
        list[IssueDataType],
        await query_application(sql)
    )

    return notifications_list


async def update(issues_data: list[IssueDataType]) -> list[IssueDataType] | None:
    sql = read_file("update_query.sql")

    notifications_ids = [issue_data["notification_id"] for issue_data in issues_data]
    notifications_list = cast(
        list[IssueDataType],
        await query_application(sql, notifications_ids)
    )

    return notifications_list


def is_solved(issue_data: IssueDataType) -> bool:
    notification_status = issue_data["notification_status"]
    return notification_status == NotificationStatus.closed.value


# Reactions

async def close_notification(event_payload: dict[str, Any]):
    """Fix the notification by closing it"""
    issue_object = event_payload["event_data"]
    notification = await Notification.get_by_id(issue_object["data"]["notification_id"])
    if notification:
        await notification.close()


reaction_options = ReactionOptions(
    issue_created=[close_notification],
    issue_updated_not_solved=[close_notification],
)

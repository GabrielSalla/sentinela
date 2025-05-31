import json
import logging
import os
from functools import partial
from typing import Any

from pydantic.dataclasses import dataclass
from pytz import timezone
from tabulate import tabulate

from configs import configs
from data_models.event_payload import EventPayload
from data_models.monitor_options import reaction_function_type
from models import Alert, AlertPriority, AlertStatus, Issue, IssueStatus, Monitor, Notification

from .. import slack

_logger = logging.getLogger("plugin.slack.notifications")

RESEND_ERRORS = [
    "message_not_found",
    "cant_update_message",
]

PRIORITY_COLOR = {
    1: "#ff0000",  # Red
    2: "#ff5500",  # Dark orange
    3: "#ffaa00",  # Light orange
    4: "#ffff00",  # Yellow
    5: "#008bff",  # Blue
    "solved": "#a0ffa0",  # Green
}


@dataclass(kw_only=True)
class SlackNotification:
    """
    The **SlackNotification** class manages sending notifications for alerts to a specified Slack
    channel.
    - `channel`: The Slack channel where notifications will be sent (e.g., `C0011223344`).
    - `title`: A title for the notification to help users to identify the problem.
    - `issues_fields`: A list of fields from the issue data to include in the notification.
    - `min_priority_to_send`: Minimum alert priority that triggers a notification. Notifications
    will be sent if the alert is not acknowledged at the current priority level and it's greater
    than or equal to this setting. Defaults to `low` (P4).
    - `mention`: Slack user or group to mention if the alert reaches a specified priority. Provide
    the Slack identifier for a user (e.g., `U0011223344`) or a group (e.g., `G0011223344`). Set to
    `None` to avoid mentioning anyone. Defaults to `None`.
    - `min_priority_to_mention`: Minimum alert priority that triggers a mention. Mentions will
    occur if the alert is not acknowledged at the current priority level and it's is greater than
    or equal to this setting. Defaults to `moderate` (P3).
    - `mention_on_update`: If set to 'False', the mention will be sent when the alert becomes
    unacknowledged and the priority is greater than or equal to the minimum priority to mention. If
    the alert is updated and the alert continues to be unacknowledged, the mention will persist.
    When set to 'True', the mention will be deleted and sent again every time alert is updated, if
    the alert is not acknowledged and the priority is greater than or equal to the minimum priority
    to mention. This option can be used as a renotification. Defaults to `False`.
    -  `issue_show_limit`: Maximum number of issues to show in the notification. If the limit is
    reached, the message `XXX more...` will be shown at the and of the issues list, where `XXX` is
    the number of issues not being shown. Defaults to `10`.
    """

    channel: str
    title: str
    issues_fields: list[str]
    min_priority_to_send: int = AlertPriority.low
    mention: str | None = None
    mention_on_update: bool = False
    min_priority_to_mention: int = AlertPriority.moderate
    issue_show_limit: int = 10

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]:
        """Get a list of events that the notification will react to"""
        handle_notification_function = partial(handle_event, notification_options=self)
        return [
            ("alert_acknowledge_dismissed", [handle_notification_function]),
            ("alert_acknowledged", [handle_notification_function]),
            ("alert_locked", [handle_notification_function]),
            ("alert_solved", [handle_notification_function]),
            ("alert_unlocked", [handle_notification_function]),
            ("alert_updated", [handle_notification_function]),
        ]


def _alert_priority_info(alert: Alert) -> str:
    """Get the alert priority information to show in the notification"""
    if alert.is_priority_acknowledged:
        priority = f"{alert.priority} ({alert.acknowledge_priority})"
    else:
        priority = f"{alert.priority}"

    return f"Priority: {priority}"


async def _issue_count_info(alert: Alert) -> str:
    """Get the alert issue count to show in the notification"""
    issues_count = await Issue.count(Issue.alert_id == alert.id, Issue.status == IssueStatus.active)
    return f"Issues: {issues_count}"


def _alert_state_info(alert: Alert) -> str | None:
    """Get the alert state to show in the notification"""
    if alert.status == AlertStatus.solved:
        return None
    if alert.locked:
        state = "Locked"
    elif alert.is_priority_acknowledged:
        state = "Acknowledged"
    else:
        return None
    return f"*{state}*"


async def _build_notification_status(
    monitor: Monitor, alert: Alert, notification_options: SlackNotification
) -> list[str]:
    """Build the status part of the notification message"""
    status = []

    if alert.status != AlertStatus.solved:
        status.append(_alert_priority_info(alert))
        status.append(await _issue_count_info(alert))

    state = _alert_state_info(alert)
    if state is not None:
        status.append(state)

    return status


async def _build_notification_timestamps(
    monitor: Monitor, alert: Alert, notification_options: SlackNotification
) -> list[str]:
    """Build the timestamps part of the notification message"""
    timestamp_format = "%Y-%m-%d %H:%M:%S"

    triggered_at = alert.created_at.astimezone(timezone(configs.time_zone))
    timestamps = [f"Triggered at: `{triggered_at.strftime(timestamp_format)}`"]
    if alert.status == AlertStatus.solved:
        solved_at = alert.solved_at.astimezone(timezone(configs.time_zone))
        timestamps.append(f"Solved at: `{solved_at.strftime(timestamp_format)}`")

    return timestamps


async def _build_issues_table(
    monitor: Monitor, alert: Alert, notification_options: SlackNotification
) -> str | None:
    """Build the issues list of the notification message"""
    if alert.status == AlertStatus.solved:
        return None

    issues = await Issue.get_all(
        Issue.alert_id == alert.id,
        Issue.status == IssueStatus.active,
        order_by=[Issue.created_at],
        limit=notification_options.issue_show_limit,
    )

    issues_count = await Issue.count(Issue.alert_id == alert.id, Issue.status == IssueStatus.active)

    table = [
        [issue.data[column] for column in notification_options.issues_fields] for issue in issues
    ]
    alert_content = tabulate(table, headers=notification_options.issues_fields)

    truncated_message = (
        f"\n{issues_count - notification_options.issue_show_limit} more..."
        if issues_count > notification_options.issue_show_limit
        else ""
    )

    return f"```\n{alert_content}\n{truncated_message}```"


async def _build_notification_buttons(
    monitor: Monitor, alert: Alert, notification_options: SlackNotification
) -> list[slack.MessageButton]:
    """Build the buttons that will be shown in the notification message"""
    buttons: list[slack.MessageButton] = []

    if os.environ.get("SLACK_WEBSOCKET_ENABLED", "false") == "false":
        return buttons

    if alert.status == AlertStatus.solved:
        return buttons

    if not alert.is_priority_acknowledged:
        buttons.append(
            slack.MessageButton(
                text="Ack", action_id=f"sentinela_ack_{alert.id}", value=f"ack {alert.id}"
            )
        )
    if not alert.locked:
        buttons.append(
            slack.MessageButton(
                text="Lock", action_id=f"sentinela_lock_{alert.id}", value=f"lock {alert.id}"
            )
        )
    if not monitor.code.issue_options.solvable:
        buttons.append(
            slack.MessageButton(
                text="Solve", action_id=f"sentinela_solve_{alert.id}", value=f"solve {alert.id}"
            )
        )

    return buttons


def _get_attachment_color(alert: Alert) -> str:
    """Get the attachment color for the alert"""
    if alert.status == AlertStatus.solved:
        return PRIORITY_COLOR["solved"]
    return PRIORITY_COLOR[alert.priority]


async def _build_attachments(
    monitor: Monitor, alert: Alert, notification_options: SlackNotification
) -> list[dict[Any, Any]]:
    """Build the message attachments that will be sent as the notification"""
    title = f"{alert.id} - {notification_options.title}"
    status = await _build_notification_status(monitor, alert, notification_options)
    timestamps = await _build_notification_timestamps(monitor, alert, notification_options)
    message = await _build_issues_table(monitor, alert, notification_options)
    buttons = await _build_notification_buttons(monitor, alert, notification_options)

    blocks = [
        slack.get_header_block(title),
        slack.get_context_block(*status) if status else None,
        slack.get_context_block(*timestamps),
        slack.get_section_block(message) if message else None,
        slack.get_actions_block(*buttons) if buttons else None,
    ]
    message_blocks = [block for block in blocks if block is not None]

    attachment_color = _get_attachment_color(alert)

    return slack.build_attachments(
        message_blocks,
        attachment_color=attachment_color,
        fallback=title,
    )


async def send_notification(
    monitor: Monitor,
    notification: Notification,
    channel: str,
    attachments: list[dict[Any, Any]],
) -> None:
    """Send the notification message to a Slack channel and save it's timestamp to the
    notification data"""
    response = await slack.send(
        channel=channel,
        attachments=attachments,
    )

    if response["ok"]:
        if notification.data is None:
            notification.data = {}

        notification.data["channel"] = response["channel"]
        notification.data["ts"] = response["ts"]

        await notification.save()
    else:
        _logger.error(
            f"Error sending slack message for {monitor} alert {notification.alert_id}: "
            f"'{json.dumps(response.data)}'"
        )


async def update_notification(
    monitor: Monitor,
    notification: Notification,
    channel: str,
    attachments: list[dict[Any, Any]],
) -> None:
    """Update a Slack message. If the update fails but the error indicates the message should be
    re-sent, send it again, otherwise just log an error"""
    ts = notification.data["ts"]
    response = await slack.update(channel=channel, ts=ts, attachments=attachments)

    if not response["ok"]:
        if response["error"] in RESEND_ERRORS:
            _logger.warning(
                f"Unable to update message for {monitor} alert {notification.alert_id} "
                f"with error '{response['error']}', resending"
            )

            # If sending a new notification message, clear the mention message so it'll be sent
            # again in the new message thread
            notification.data["mention_ts"] = None

            await send_notification(
                monitor=monitor,
                notification=notification,
                channel=channel,
                attachments=attachments,
            )
        else:
            _logger.error(
                f"Error updating slack message for {monitor} alert {notification.alert_id}: "
                f"'{json.dumps(response.data)}'"
            )


async def _delete_notification(notification: Notification) -> None:
    """Delete a Slack message"""
    channel = notification.data.get("channel")
    ts = notification.data.get("ts")

    if channel is not None and ts is not None:
        await slack.delete(channel=channel, ts=ts)

    notification.data["ts"] = None
    notification.data["channel"] = None
    await notification.save()


def _should_have_mention(alert: Alert, notification_options: SlackNotification) -> bool:
    """Check if the notification should have a mention message"""
    mention_conditions = [
        alert.status == AlertStatus.active,
        not alert.is_priority_acknowledged,
        alert.priority <= notification_options.min_priority_to_mention,
    ]
    return all(mention_conditions)


async def _send_mention(
    monitor: Monitor, notification: Notification, channel: str, title: str, mention: str
) -> None:
    """Send a mention message to a message thread"""
    response = await slack.send(
        channel=channel,
        thread_ts=notification.data["ts"],
        text=f"<@{mention}> Alert *{title}* not acknowledged",
    )

    if response["ok"]:
        notification.data["mention_ts"] = response["ts"]
        await notification.save()
    else:
        _logger.error(
            f"Error sending notification mention for {monitor} alert {notification.alert_id}: "
            f"'{json.dumps(response.data)}'"
        )


async def _delete_mention(notification: Notification) -> None:
    """Send a mention message to a message thread"""
    if notification.data is None:
        return

    channel = notification.data.get("channel")
    mention_ts = notification.data.get("mention_ts")

    if channel is not None and mention_ts is not None:
        await slack.delete(channel=channel, ts=mention_ts)

    notification.data["mention_ts"] = None
    await notification.save()


async def notification_mention(
    monitor: Monitor,
    alert: Alert,
    notification: Notification,
    notification_options: SlackNotification,
) -> None:
    """Send a mention to the notification's message thread, to alert who needs to be alerted. The
    mention message will be deleted if it's not necessary anymore"""
    if notification_options.mention is None:
        return

    if notification.data is None:
        return

    if notification.data.get("ts") is None:
        return

    # Check if should have a mention message
    if not _should_have_mention(alert, notification_options):
        await _delete_mention(notification)
        return

    # If the mention should be sent on update, delete the previous mention message
    if notification_options.mention_on_update:
        await _delete_mention(notification)

    # If the mention message already exists, do not send it again
    if notification.data.get("mention_ts") is not None:
        return

    await _send_mention(
        monitor,
        notification,
        notification_options.channel,
        notification_options.title,
        notification_options.mention,
    )


async def _handle_slack_notification(
    alert_id: int,
    notification_options: SlackNotification,
) -> None:
    """Handle the Slack notification for an alert"""
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        return

    notification = await Notification.get(
        Notification.monitor_id == alert.monitor_id,
        Notification.alert_id == alert.id,
        Notification.target == "slack",
    )

    # Only continue if the notification already exists or if the alert priority triggers a new
    # notification
    if notification is None:
        # Lower number for priority is more important, so this operation is reversed
        if alert.priority > notification_options.min_priority_to_send:
            return
        if alert.status == AlertStatus.solved:
            return

        notification = await Notification.create(
            monitor_id=alert.monitor_id, alert_id=alert.id, target="slack"
        )

    if alert.status == AlertStatus.solved:
        await notification.close()

    monitor = await Monitor.get_by_id(alert.monitor_id)
    # This check is just to make the typing check happy, as the monitor must exist because of the
    # alert's 'monitor_id' foreign key
    if monitor is None:
        return  # pragma: no cover

    attachments = await _build_attachments(monitor, alert, notification_options)

    if notification.data is not None and notification.data.get("ts") is not None:
        await update_notification(
            monitor=monitor,
            notification=notification,
            channel=notification_options.channel,
            attachments=attachments,
        )
    else:
        await send_notification(
            monitor=monitor,
            notification=notification,
            channel=notification_options.channel,
            attachments=attachments,
        )

    await notification_mention(
        monitor=monitor,
        alert=alert,
        notification=notification,
        notification_options=notification_options,
    )


async def handle_event(event: EventPayload, notification_options: SlackNotification) -> None:
    """Handle the Slack notification for an alert"""
    if event.event_source != "alert":
        raise ValueError(f"Invalid event source '{event.event_source}'")

    await _handle_slack_notification(event.event_source_id, notification_options)


async def clear_slack_notification(notification: Notification) -> None:
    """Delete the notification message and mention message"""
    await _delete_notification(notification)
    await _delete_mention(notification)

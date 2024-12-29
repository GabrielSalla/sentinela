import logging
from typing import Any, cast

import registry
from models import Monitor, Notification, NotificationStatus
from utils.async_tools import do_concurrently

from ..notifications import slack_notification

_logger = logging.getLogger("plugin.slack.actions")


async def _resend_notification(notification: Notification):
    """Clear a single notification and send it again"""
    await registry.wait_monitor_loaded(notification.monitor_id)

    monitor = await Monitor.get_by_id(notification.monitor_id)
    if monitor is None:
        return  # pragma: no cover

    # Get the SlackNotification option from the monitor code
    notification_option = None
    for notification_option in monitor.code.notification_options:
        if isinstance(notification_option, slack_notification.SlackNotification):
            break
    if notification_option is None:
        _logger.warning(f"No 'SlackNotification' option for {monitor}")
        return

    # Clear the notification and send it again
    await slack_notification.clear_slack_notification(notification)
    await slack_notification.slack_notification(
        event_payload={
            "event_data": {
                "id": notification.alert_id,
            }
        },
        notification_options=cast(slack_notification.SlackNotification, notification_option),
    )


async def resend_notifications(message_payload: dict[Any, Any]):
    """Clear all the notifications for the channel and update all active alerts to queue events to
    send the notifications again"""
    # Get all active notifications for the channel
    notifications = await Notification.get_all(
        Notification.status == NotificationStatus.active,
        Notification.target == "slack",
        Notification.data["channel"].astext == message_payload["slack_channel"],
    )

    await do_concurrently(*[
        _resend_notification(notification)
        for notification in notifications
    ])

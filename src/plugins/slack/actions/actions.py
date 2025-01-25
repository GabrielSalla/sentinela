import logging
from typing import Any

import registry
from models import Monitor, Notification, NotificationStatus
from utils.async_tools import do_concurrently

from ..notifications import slack_notification

_logger = logging.getLogger("plugin.slack.actions")


async def _resend_notification(notification: Notification) -> None:
    """Clear a single notification and send it again"""
    await registry.wait_monitor_loaded(notification.monitor_id)

    monitor = await Monitor.get_by_id(notification.monitor_id)
    if monitor is None:
        return  # pragma: no cover

    # Get the SlackNotification option from the monitor code
    for notification_option in monitor.code.notification_options:
        if not isinstance(notification_option, slack_notification.SlackNotification):
            continue

        if notification_option.channel == notification.data["channel"]:
            # Clear the notification and send it again
            await slack_notification.clear_slack_notification(notification)
            await slack_notification.slack_notification(
                event_payload={
                    "event_data": {
                        "id": notification.alert_id,
                    }
                },
                notification_options=notification_option,
            )
            break
    else:
        _logger.warning(f"No 'SlackNotification' option for {monitor}")


async def resend_notifications(message_payload: dict[Any, Any]) -> None:
    """Clear all the notifications for the channel and update all active alerts to queue events to
    send the notifications again"""
    # Get all active notifications for the channel
    notifications = await Notification.get_all(
        Notification.status == NotificationStatus.active,
        Notification.target == "slack",
        Notification.data["channel"].astext == message_payload["slack_channel"],
    )

    await do_concurrently(*[_resend_notification(notification) for notification in notifications])

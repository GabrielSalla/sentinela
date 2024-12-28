from typing import Any

import registry
from models import Alert, Notification, NotificationStatus
from utils.async_tools import do_concurrently

from ..slack_notification import clear_slack_notification


async def resend_notifications(message_payload: dict[Any, Any]):
    """Clear all the notifications for the channel and update all active alerts to queue events to
    send the notifications again"""
    # Get all active notifications for the channel
    notifications = await Notification.get_all(
        Notification.status == NotificationStatus.active,
        Notification.target == "slack",
        Notification.data["channel"].astext == message_payload["slack_channel"],
    )

    if len(notifications) == 0:
        return

    monitors_ids = {notification.monitor_id for notification in notifications}
    for monitor_id in monitors_ids:
        await registry.wait_monitor_loaded(monitor_id)

    await do_concurrently(*[
        clear_slack_notification(notification)
        for notification in notifications
    ])

    alert_ids = list({notification.alert_id for notification in notifications})
    alerts = await Alert.get_all(Alert.id.in_(alert_ids))
    await do_concurrently(*[alert.update() for alert in alerts])

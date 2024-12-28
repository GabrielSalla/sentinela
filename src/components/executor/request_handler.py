import asyncio
import json
import logging
import traceback
from typing import Any

import registry as registry
from base_exception import BaseSentinelaException
from configs import configs
from models import Alert, Issue, Notification, NotificationStatus
from services.slack import clear_slack_notification
from utils.async_tools import do_concurrently

_logger = logging.getLogger("request_handler")


async def alert_acknowledge(message_payload: dict[Any, Any]):
    """Acknowledge an alert"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.acknowledge()


async def alert_lock(message_payload: dict[Any, Any]):
    """Lock an alert"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.lock()


async def alert_solve(message_payload: dict[Any, Any]):
    """Solve all alert's issues"""
    alert_id = message_payload["target_id"]
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        _logger.info(f"Alert '{alert_id}' not found")
        return
    await registry.wait_monitor_loaded(alert.monitor_id)
    await alert.solve_issues()


async def issue_drop(message_payload: dict[Any, Any]):
    """Drop an issue"""
    issue_id = message_payload["target_id"]
    issue = await Issue.get_by_id(issue_id)
    if issue is None:
        _logger.info(f"Issue '{issue_id}' not found")
        return
    await registry.wait_monitor_loaded(issue.monitor_id)
    await issue.drop()


async def resend_slack_notifications(message_payload: dict[Any, Any]):
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


actions = {
    "alert_acknowledge": alert_acknowledge,
    "alert_lock": alert_lock,
    "alert_solve": alert_solve,
    "issue_drop": issue_drop,
    "resend_slack_notifications": resend_slack_notifications,
}


async def run(message: dict[Any, Any]):
    """Process a received request"""
    message_payload = message["payload"]
    action_name = message_payload["action"]

    action = actions.get(action_name)

    if action is None:
        _logger.warning(f"Got request with unknown action '{json.dumps(message_payload)}'")
        return

    try:
        await asyncio.wait_for(action(message_payload), configs.executor_request_timeout)
    except asyncio.TimeoutError:
        _logger.error(f"Timed out executing request '{json.dumps(message_payload)}'")
    except BaseSentinelaException as e:
        raise e
    except Exception:
        _logger.error(f"Error executing request '{json.dumps(message_payload)}'")
        _logger.error(traceback.format_exc().strip())

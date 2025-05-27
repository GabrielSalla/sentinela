"""
Search for active notifications linked to alerts that have already been solved and closes the
identified notifications.
"""

import logging

import databases
from models import Notification

from .constants import SQL_FILES_PATH

_logger = logging.getLogger("procedures.notifications_alert_solved")


async def notifications_alert_solved() -> None:
    with open(SQL_FILES_PATH / "notification_alert_solved.sql") as file:
        query = file.read()

    result = await databases.query_application(query)

    if result is None:
        _logger.error("Error with query result")
        return

    for notification_info in result:
        notification = await Notification.get_by_id(notification_info["id"])
        if notification is None:
            _logger.error(f"Notification with id '{notification_info['id']}' not found")
            continue

        await notification.close()
        _logger.warning(f"{notification} closed")

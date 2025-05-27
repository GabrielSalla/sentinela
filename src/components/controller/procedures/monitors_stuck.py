"""
Searches for monitors that are stuck in a running state for too long without a heartbeat and resets
it's queued and running attributes to 'False' to allow them to be queued again.
"""

import logging

import databases
from models import Monitor

from .constants import SQL_FILES_PATH

_logger = logging.getLogger("procedures.monitors_stuck")


async def monitors_stuck(time_tolerance: int) -> None:
    with open(SQL_FILES_PATH / "monitors_stuck.sql") as file:
        query = file.read()

    result = await databases.query_application(query, time_tolerance)

    if result is None:
        _logger.error("Error with query result")
        return

    for monitor_info in result:
        monitor = await Monitor.get_by_id(monitor_info["id"])

        if monitor is None:
            _logger.error(f"Monitor with id '{monitor_info['id']}' not found")
            continue

        await monitor.set_queued(False)
        await monitor.set_running(False)

        _logger.warning(f"{monitor} was stuck and now it's fixed")

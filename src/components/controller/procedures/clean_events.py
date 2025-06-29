"""
Clean old events from database.
"""

import logging

import databases

from .constants import SQL_FILES_PATH

_logger = logging.getLogger("procedures.clean_events")


async def monitors_stuck(retention_days: int) -> None:
    with open(SQL_FILES_PATH / "clean_events.sql") as file:
        query = file.read()

    await databases.execute_application(query, retention_days)

"""
Clean old events from the production database to save on storage.
"""

import logging

import databases

from .constants import SQL_FILES_PATH

_logger = logging.getLogger("procedures.clean_old_events")


async def clean_old_events(age_days: int) -> None:
    with open(SQL_FILES_PATH / "clean_old_events.sql") as file:
        query = file.read()

    await databases.execute_application(query, age_days)

    _logger.info(f"Events older than {age_days} cleaned from the database")

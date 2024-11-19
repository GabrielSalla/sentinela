import datetime
from math import ceil

from croniter import croniter
from pytz import timezone

from src.configs import configs


def now():
    """Get a datetime object with the current timestamp at the configured timezone"""
    return datetime.datetime.now(tz=timezone(configs.time_zone))


def format_datetime_iso(timestamp: datetime.datetime | None) -> str | None:
    return timestamp.isoformat(timespec="milliseconds") if timestamp is not None else None


def is_triggered(
    cron_configuration: str,
    last_trigger: datetime.datetime,
    datetime_reference: datetime.datetime | None = None,
) -> bool:
    """Check if a cron configuration is considered as trigger based on the latest trigger and a
    reference timestamp"""
    # Use the current timestamp as reference if none was provided
    if datetime_reference is None:
        datetime_reference = now()

    cron = croniter(cron_configuration, datetime_reference)
    last_expected_trigger: datetime.datetime = cron.get_prev(datetime.datetime)

    # If the last trigger is before the last expected trigger, it must be triggered
    return last_trigger < last_expected_trigger


def time_since(
    timestamp: datetime.datetime | None, reference: datetime.datetime | None = None
) -> float:
    """Get the time in seconds since a timestamp"""
    if timestamp is None:
        return -1

    if reference is None:
        reference = now()

    return (reference - timestamp).total_seconds()


def time_until_next_trigger(
    cron_configuration: str, datetime_reference: datetime.datetime | None = None
) -> int:
    """Get the time in seconds until the next trigger based on a cron configuration"""
    # Use the current timestamp as reference if none was provided
    if datetime_reference is None:
        datetime_reference = now()

    cron = croniter(cron_configuration, datetime_reference)
    next_expected_trigger: datetime.datetime = cron.get_next(datetime.datetime)
    interval = next_expected_trigger - datetime_reference
    return ceil(interval.total_seconds())

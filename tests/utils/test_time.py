import datetime
import time

import pytest
from pytz import timezone

from configs import configs
from utils.time import (
    format_datetime_iso,
    is_triggered,
    localize,
    now,
    time_since,
    time_until_next_trigger,
)


@pytest.mark.parametrize("local_timezone", ["UTC", "America/Sao_Paulo", "Europe/London"])
def test_now(monkeypatch, local_timezone):
    """'now' should return the current datetime in the configured timezone"""
    monkeypatch.setattr(configs, "time_zone", local_timezone)

    now_1 = now()
    time.sleep(0.2)
    now_2 = now()

    assert now_1.tzinfo is not None
    assert now_2.tzinfo is not None

    assert now_1 == now_1.astimezone(timezone(local_timezone))
    assert now_2 == now_2.astimezone(timezone(local_timezone))
    time_diff = now_2 - now_1
    assert time_diff < datetime.timedelta(milliseconds=201)


@pytest.mark.parametrize(
    "dt, tz, expected_dt",
    [
        (
            timezone("utc").localize(datetime.datetime(2024, 1, 1, 12, 0, 0)),
            "utc",
            timezone("utc").localize(datetime.datetime(2024, 1, 1, 12, 0, 0)),
        ),
        (
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 12, 0, 0)),
            "utc",
            timezone("utc").localize(datetime.datetime(2024, 1, 1, 15, 0, 0)),
        ),
        (
            timezone("utc").localize(datetime.datetime(2024, 1, 1, 12, 34, 0)),
            "America/Sao_Paulo",
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 9, 34, 0)),
        ),
        (
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 12, 0, 0)),
            "America/Sao_Paulo",
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 12, 0, 0)),
        ),
    ],
)
def test_localize(monkeypatch, dt, tz, expected_dt):
    """'localize' should convert a datetime to the configured timezone"""
    monkeypatch.setattr(configs, "time_zone", tz)

    assert localize(dt) == expected_dt


@pytest.mark.parametrize(
    "timestamp, expected_result",
    [
        (
            datetime.datetime(2024, 1, 1, 12, 34, 56, 789000, tzinfo=datetime.timezone.utc),
            "2024-01-01T12:34:56.789+00:00",
        ),
        (
            datetime.datetime(1991, 12, 31, 11, 22, 33, 444000, tzinfo=datetime.timezone.utc),
            "1991-12-31T11:22:33.444+00:00",
        ),
        (datetime.datetime(2024, 1, 1, 12, 34, 56, 789000), "2024-01-01T12:34:56.789"),
        (datetime.datetime(1991, 12, 31, 11, 22, 33, 444000), "1991-12-31T11:22:33.444"),
        (None, None),
    ],
)
def test_format_datetime_iso(timestamp, expected_result):
    """'format_datetime_iso' should return a string with the timestamp in ISO format"""
    result = format_datetime_iso(timestamp)
    assert result == expected_result


@pytest.mark.parametrize(
    "cron_configuration, last_trigger, datetime_reference, expected_result",
    [
        (
            "* * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 1, 0, 0, 59),
            False,
        ),
        (
            "* * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 1, 0, 1, 1),
            True,
        ),
        (
            "* * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 1, 0, 1, 59),
            True,
        ),
        (
            "*/5 * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 1, 0, 4, 59),
            False,
        ),
        (
            "*/5 * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 1, 0, 5, 1),
            True,
        ),
        (
            "* * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone("UTC")),
            datetime.datetime(2024, 1, 1, 0, 0, 59, tzinfo=timezone("UTC")),
            False,
        ),
        (
            "* * * * *",
            datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone("UTC")),
            datetime.datetime(2024, 1, 1, 0, 1, 1, tzinfo=timezone("UTC")),
            True,
        ),
        (
            "* * * * *",
            timezone("UTC").localize(datetime.datetime(2024, 1, 10, 0, 0, 0)),
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 9, 21, 0, 59)),
            False,
        ),
        (
            "* * * * *",
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 9, 21, 0, 0)),
            timezone("UTC").localize(datetime.datetime(2024, 1, 10, 0, 1, 1)),
            True,
        ),
        # Cron should be based on the reference datetime
        (
            "0 */2 * * *",
            timezone("utc").localize(datetime.datetime(2024, 1, 10, 3, 0, 0)),
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 10, 1, 59, 0)),
            False,
        ),
        (
            "0 */2 * * *",
            timezone("utc").localize(datetime.datetime(2024, 1, 10, 3, 0, 0)),
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 10, 2, 0, 1)),
            True,
        ),
    ],
)
def test_is_triggered(cron_configuration, last_trigger, datetime_reference, expected_result):
    """'is_triggered' should return 'True' if the cron configuration is triggered based on the last
    trigger and the reference datetime"""
    result = is_triggered(cron_configuration, last_trigger, datetime_reference)
    assert result == expected_result


@pytest.mark.parametrize(
    "timestamp, reference, expected_result",
    [
        (datetime.datetime(2024, 1, 1, 1, 0, 0), datetime.datetime(2024, 1, 1, 1, 0, 45), 45),
        (datetime.datetime(2024, 1, 1, 1, 0, 0), datetime.datetime(2024, 1, 1, 1, 15, 0), 15 * 60),
        (
            datetime.datetime(2024, 1, 1, 1, 0, 0),
            datetime.datetime(2024, 1, 1, 4, 0, 0),
            3 * 60 * 60,
        ),
        (
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 10, 0, 0, 0),
            9 * 60 * 60 * 24,
        ),
        (
            datetime.datetime(2024, 1, 1, 0, 0, 0),
            datetime.datetime(2024, 1, 3, 2, 34, 56),
            2 * 60 * 60 * 24 + 2 * 60 * 60 + 34 * 60 + 56,
        ),
        (
            timezone("UTC").localize(datetime.datetime(2024, 1, 1, 1, 0, 0)),
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 1, 0, 0)),
            3 * 60 * 60,
        ),
        (
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 21, 0, 0)),
            timezone("UTC").localize(datetime.datetime(2024, 1, 10, 0, 0, 0)),
            8 * 60 * 60 * 24,
        ),
        (None, datetime.datetime(2024, 1, 1, 0, 0, 0), -1),
    ],
)
def test_time_since(timestamp, reference, expected_result):
    """'time_since' should return the time difference in seconds between the timestamp and the
    reference datetime"""
    result = time_since(timestamp, reference)
    assert result == expected_result


@pytest.mark.parametrize(
    "cron_configuration, datetime_reference, expected_result",
    [
        ("* * * * *", datetime.datetime(2024, 1, 1, 0, 0, 0), 60),
        ("* * * * *", datetime.datetime(2024, 1, 1, 0, 0, 32), 28),
        ("*/5 * * * *", datetime.datetime(2024, 1, 1, 0, 3, 15), 105),
        ("*/5 * * * *", datetime.datetime(2024, 1, 1, 0, 3, 15, 999), 105),
        # Cron should be based on the reference datetime
        (
            "0 */2 * * *",
            timezone("UTC").localize(datetime.datetime(2024, 1, 1, 0, 3, 15)),
            45 + 56 * 60 + 60 * 60,
        ),
        (
            "0 */3 * * *",
            timezone("America/Sao_Paulo").localize(datetime.datetime(2024, 1, 1, 0, 35, 41)),
            19 + 24 * 60 + 2 * 60 * 60,
        ),
    ],
)
def test_time_until_next_trigger(cron_configuration, datetime_reference, expected_result):
    """'time_until_next_trigger' should return the time in seconds until the next trigger based on
    the reference datetime"""
    result = time_until_next_trigger(cron_configuration, datetime_reference)
    assert result == expected_result

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import components.controller.procedures.monitors_stuck as monitors_stuck
from models import Monitor
from tests.test_utils import assert_message_in_log, assert_message_not_in_log
from utils.time import now

pytestmark = pytest.mark.asyncio(loop_scope="session")


def get_time(reference: str) -> datetime | None:
    values = {
        "now": now(),
        "ten_seconds_ago": now() - timedelta(seconds=11),
        "five_minutes_ago": now() - timedelta(seconds=301),
    }
    return values.get(reference)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("queued", [False, True])
@pytest.mark.parametrize("running", [False, True])
@pytest.mark.parametrize("last_heartbeat", [None, "now", "ten_seconds_ago"])
async def test_monitors_stuck(
    caplog,
    sample_monitor: Monitor,
    enabled,
    queued,
    running,
    last_heartbeat,
):
    """'monitors_stuck' should fix monitors that are stuck"""
    sample_monitor.enabled = enabled
    sample_monitor.queued = queued
    sample_monitor.running = running
    sample_monitor.last_heartbeat = get_time(last_heartbeat)  # type:ignore[assignment]
    await sample_monitor.save()

    await monitors_stuck.monitors_stuck(time_tolerance=10)

    await sample_monitor.refresh()

    if not enabled:
        triggered = False
    elif last_heartbeat is None:
        triggered = False
    elif last_heartbeat == "now":
        triggered = False
    else:
        triggered = queued or running

    if triggered:
        assert not sample_monitor.queued
        assert not sample_monitor.running
        assert_message_in_log(caplog, f"{sample_monitor} was stuck and now it's fixed")
    else:
        assert sample_monitor.queued == queued
        assert sample_monitor.running == running
        assert_message_not_in_log(caplog, f"{sample_monitor} was stuck and now it's fixed")


async def test_monitors_stuck_query_result_none(caplog, monkeypatch):
    """'monitors_stuck' should log an error if the query result is None"""
    monkeypatch.setattr(monitors_stuck.databases, "query_application", AsyncMock(return_value=None))

    await monitors_stuck.monitors_stuck(time_tolerance=300)

    assert_message_in_log(caplog, "Error with query result")


async def test_monitors_stuck_monitor_not_found(caplog, monkeypatch):
    """'monitors_stuck' should log an error if the monitor is not found"""
    monkeypatch.setattr(
        monitors_stuck.databases, "query_application", AsyncMock(return_value=[{"id": 99999999}])
    )

    await monitors_stuck.monitors_stuck(time_tolerance=300)

    assert_message_in_log(caplog, "Monitor with id '99999999' not found")


async def test_monitors_stuck_monitor_not_found_2_results(
    caplog, monkeypatch, sample_monitor: Monitor
):
    """'monitors_stuck' should log an error if one monitor is not found but should continue with
    the other monitors"""
    monkeypatch.setattr(
        monitors_stuck.databases,
        "query_application",
        AsyncMock(return_value=[{"id": 99999999}, {"id": sample_monitor.id}]),
    )

    await monitors_stuck.monitors_stuck(time_tolerance=300)

    assert_message_in_log(caplog, "Monitor with id '99999999' not found")
    assert_message_in_log(caplog, f"{sample_monitor} was stuck and now it's fixed")

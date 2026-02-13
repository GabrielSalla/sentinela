import asyncio
import time
from collections import deque
from unittest.mock import MagicMock

import pytest

import components.heartbeat.heartbeat as heartbeat
import utils.app as app
from configs import configs

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "timestamps, threshold, expected_result",
    [
        (deque([100]), 1, False),
        (deque([100, 101]), 1, False),
        (deque([100, 102]), 1, True),
        (deque([1, 3, 5, 7, 9]), 2, False),
        (deque([1, 3, 5, 7, 10]), 2, True),
    ],
)
async def test_is_heartbeat_delayed(timestamps, threshold, expected_result):
    """'is_heartbeat_delayed' should return True when average latency exceeds threshold"""
    assert heartbeat._is_heartbeat_delayed(timestamps, threshold) is expected_result


async def test_run(mocker, monkeypatch):
    """'run' should append the current timestamp while app is running"""
    monkeypatch.setattr(configs, "heartbeat_time", 0.05)
    heartbeat_logger_warning_spy: MagicMock = mocker.spy(heartbeat._logger, "warning")

    task = asyncio.create_task(heartbeat.run())

    await asyncio.sleep(0.1)
    assert heartbeat_logger_warning_spy.call_count == 0
    time.sleep(0.1)
    await asyncio.sleep(0)
    assert heartbeat_logger_warning_spy.call_count == 1

    app.stop()
    await asyncio.wait_for(task, timeout=0.1)


async def test_run_cooldown(mocker, monkeypatch):
    """'run' should respect the cooldown period between warnings when heartbeat is delayed"""
    monkeypatch.setattr(configs, "heartbeat_time", 0.05)
    heartbeat_logger_warning_spy: MagicMock = mocker.spy(heartbeat._logger, "warning")

    task = asyncio.create_task(heartbeat.run())

    await asyncio.sleep(0.1)
    time.sleep(0.1)
    await asyncio.sleep(0)
    assert heartbeat_logger_warning_spy.call_count == 1
    time.sleep(0.1)
    await asyncio.sleep(0)
    assert heartbeat_logger_warning_spy.call_count == 1

    app.stop()
    await asyncio.wait_for(task, timeout=0.1)

import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import components.controller.controller as controller
import components.monitors_loader.monitors_loader as monitors_loader
import message_queue as message_queue
import registry as registry
import utils.app as app
import utils.time as time_utils
from configs import configs
from models import Monitor
from models.exceptions import MonitorQueueException
from tests.message_queue.utils import get_queue_items
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "started_at, last_loop_at, last_monitor_processed_at, expected_result",
    [
        (datetime(2024, 1, 1, 12, 34, 0, tzinfo=timezone.utc), None, None, ({}, [])),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            None,
            None,
            (
                {"last_loop_at": None, "last_monitor_processed_at": None},
                ["loop_not_running", "no_recent_monitor_processed"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 33, 1, tzinfo=timezone.utc),
            None,
            (
                {
                    "last_loop_at": "2024-01-01T12:33:01.000+00:00",
                    "last_monitor_processed_at": None,
                },
                ["no_recent_monitor_processed"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            None,
            datetime(2024, 1, 1, 12, 33, 1, tzinfo=timezone.utc),
            (
                {
                    "last_loop_at": None,
                    "last_monitor_processed_at": "2024-01-01T12:33:01.000+00:00",
                },
                ["loop_not_running"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 33, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 32, 2, tzinfo=timezone.utc),
            (
                {
                    "last_loop_at": "2024-01-01T12:33:01.000+00:00",
                    "last_monitor_processed_at": "2024-01-01T12:32:02.000+00:00",
                },
                [],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 20, 3, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 32, 4, tzinfo=timezone.utc),
            (
                {
                    "last_loop_at": "2024-01-01T12:20:03.000+00:00",
                    "last_monitor_processed_at": "2024-01-01T12:32:04.000+00:00",
                },
                ["loop_not_running"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 20, 5, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 19, 6, tzinfo=timezone.utc),
            (
                {
                    "last_loop_at": "2024-01-01T12:20:05.000+00:00",
                    "last_monitor_processed_at": "2024-01-01T12:19:06.000+00:00",
                },
                ["loop_not_running", "no_recent_monitor_processed"],
            ),
        ),
    ],
)
async def test_diagnostics(
    monkeypatch, started_at, last_loop_at, last_monitor_processed_at, expected_result
):
    """'diagnostics' should return the status and issues for the controller, based on it's
    internal variables"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(controller, "started_at", started_at, raising=False)
    monkeypatch.setattr(controller, "last_loop_at", last_loop_at, raising=False)
    monkeypatch.setattr(
        controller, "last_monitor_processed_at", last_monitor_processed_at, raising=False
    )

    result = await controller.diagnostics()
    assert result == expected_result


async def test_process_monitor(monkeypatch, sample_monitor: Monitor):
    """'_process_monitor' should process the monitor and update the processed timestamp"""
    processed_at = datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    process_mock = AsyncMock()
    monkeypatch.setattr(sample_monitor, "process", process_mock)
    monkeypatch.setattr(controller, "now", lambda: processed_at)

    await controller._process_monitor(sample_monitor)

    process_mock.assert_awaited_once()
    assert controller.last_monitor_processed_at == processed_at


async def test_process_monitor_queue_error(monkeypatch, sample_monitor: Monitor):
    """'_process_monitor' should handle queue errors and update the processed timestamp"""
    processed_at = datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    process_mock = AsyncMock(side_effect=MonitorQueueException())
    monkeypatch.setattr(sample_monitor, "process", process_mock)
    monkeypatch.setattr(controller, "now", lambda: processed_at)

    await controller._process_monitor(sample_monitor)

    process_mock.assert_awaited_once()
    assert controller.last_monitor_processed_at == processed_at


async def test_run_task(monkeypatch, sample_monitor: Monitor):
    """'_run_task' should process the monitor and release the semaphore"""
    semaphore = asyncio.Semaphore(1)

    process_monitor_mock = AsyncMock()
    monkeypatch.setattr(controller, "_process_monitor", process_monitor_mock)

    await controller._run_task(semaphore, sample_monitor)

    process_monitor_mock.assert_awaited_once_with(sample_monitor)


async def test_run_task_wait_semaphore(monkeypatch, sample_monitor: Monitor):
    """'_run_task' should wait for the semaphore to be available before processing the monitor"""
    semaphore = asyncio.Semaphore(1)

    process_monitor_mock = AsyncMock()
    monkeypatch.setattr(controller, "_process_monitor", process_monitor_mock)

    async with semaphore:
        task = asyncio.create_task(controller._run_task(semaphore, sample_monitor))
        await asyncio.sleep(0.1)
        assert not task.done()
        process_monitor_mock.assert_not_called()

    await asyncio.sleep(0.1)
    assert task.done()
    process_monitor_mock.assert_awaited_once_with(sample_monitor)


async def test_create_process_task(caplog, sample_monitor: Monitor):
    """'_create_process_task' should create a task that processes the monitor"""
    semaphore = asyncio.Semaphore(1)

    task = await controller._create_process_task(semaphore, sample_monitor)
    await task

    assert task is not None
    assert_message_in_log(caplog, "Triggered ['search', 'update']")


async def test_create_process_task_monitor_not_registered(caplog, sample_monitor: Monitor):
    """'_create_process_task' should return 'None' if the monitor is not registered"""
    registry.registry._monitors = {}
    semaphore = asyncio.Semaphore(1)

    task = await controller._create_process_task(semaphore, sample_monitor)

    assert task is None
    assert_message_in_log(caplog, f"Monitor {sample_monitor} is not registered, skipping")


async def test_create_process_task_semaphore_wait(caplog, sample_monitor: Monitor):
    """'_create_process_task' should wait for the semaphore to be available before processing the
    monitor"""
    semaphore = asyncio.Semaphore(1)

    async with semaphore:
        wait_semaphore_task = asyncio.create_task(
            controller._create_process_task(semaphore, sample_monitor)
        )
        await asyncio.sleep(0.1)
        assert not wait_semaphore_task.done()

    await asyncio.sleep(0.1)
    assert wait_semaphore_task.done()

    run_task_task = await wait_semaphore_task
    await run_task_task

    assert_message_in_log(caplog, "Triggered ['search', 'update']")


async def test_run(monkeypatch, clear_queue, clear_database):
    """Integration test of the 'run' method. It should loop through all monitors, create them in
    the database and process them accordingly. When the loop stops, it should stop automatically"""
    monkeypatch.setattr(configs, "load_example_monitors", True)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/example_monitors/internal")
    monkeypatch.setattr(configs, "example_monitors_path", "tests/example_monitors/others")

    run_procedures_mock = AsyncMock()
    monkeypatch.setattr(controller, "run_procedures", run_procedures_mock)

    # Run the controller for a while then stop it
    await monitors_loader._register_monitors()
    controller_task = asyncio.create_task(controller.run())
    await asyncio.sleep(0.2)

    # Controller is still waiting for the monitors to be ready, so no messages were queued
    queue_items = get_queue_items()
    assert len(queue_items) == 0

    # Load the monitors and wait for a while
    await monitors_loader._load_monitors(None)
    await asyncio.sleep(0.2)

    # Stop the app and wait for the controller task
    app.stop()
    await asyncio.wait_for(controller_task, timeout=0.5)

    assert controller_task.done()

    # Assert the _monitors_id_name_map was populated when the monitors were created in the database
    monitors_instances = await Monitor.get_all(Monitor.enabled)
    assert len(monitors_instances) == 3

    # Assert the "run_procedures" function was executed
    run_procedures_mock.assert_awaited_once()

    # Assert the tasks were queued
    queue_items_set = set(get_queue_items())

    assert queue_items_set == {
        json.dumps(
            {
                "type": "process_monitor",
                "payload": {
                    "monitor_id": monitors_instances[0].id,
                    "tasks": ["search", "update"],
                },
            }
        ),
        json.dumps(
            {
                "type": "process_monitor",
                "payload": {
                    "monitor_id": monitors_instances[1].id,
                    "tasks": ["search", "update"],
                },
            }
        ),
        json.dumps(
            {
                "type": "process_monitor",
                "payload": {
                    "monitor_id": monitors_instances[2].id,
                    "tasks": ["search", "update"],
                },
            }
        ),
    }


async def test_run_no_sleep(mocker, monkeypatch):
    """'run' should not sleep if the controller completes the loop and another one is already
    triggered"""
    monkeypatch.setattr(configs, "load_example_monitors", True)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/example_monitors/internal")
    monkeypatch.setattr(configs, "example_monitors_path", "tests/example_monitors/others")

    run_procedures_mock = AsyncMock()
    monkeypatch.setattr(controller, "run_procedures", run_procedures_mock)

    monkeypatch.setattr(controller, "is_triggered", lambda *args, **kwargs: True)

    sleep_spy: AsyncMock = mocker.spy(app, "sleep")

    # Run the controller for a while then stop it
    await monitors_loader._register_monitors()
    await monitors_loader._load_monitors(None)

    controller_task = asyncio.create_task(controller.run())
    await asyncio.sleep(0.5)

    # Stop the app and wait for the controller task
    app.stop()
    await asyncio.wait_for(controller_task, timeout=0.5)

    sleep_spy.assert_not_called()


async def test_run_current_task_error(caplog, monkeypatch):
    """'run' should log an error if it can't get the current task and finish the execution"""
    monkeypatch.setattr(asyncio, "current_task", lambda: None)

    await asyncio.wait_for(controller.run(), timeout=0.1)
    assert_message_in_log(caplog, "Could not get the current asyncio task, finishing")


async def test_run_monitors_not_ready(caplog, monkeypatch, mocker):
    """'run' should loop until the monitors are ready, logging warning messages if they are not"""
    monkeypatch.setattr(configs, "load_example_monitors", True)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/example_monitors/internal")
    monkeypatch.setattr(configs, "example_monitors_path", "tests/example_monitors/others")
    monkeypatch.setattr(registry.registry, "MONITORS_READY_TIMEOUT", 0.1)

    # Run the controller for a while then stop it
    await monitors_loader._register_monitors()
    await monitors_loader._load_monitors(None)
    registry.monitors_ready.clear()

    controller_task = asyncio.create_task(controller.run())
    await asyncio.sleep(0.31)
    controller_task.cancel()

    assert_message_in_log(caplog, "MonitorsLoadError: Waiting for monitors to be ready timed out")


async def test_run_monitors_not_registered(caplog, monkeypatch, mocker):
    """'run' should handle monitors that are not registered"""
    monkeypatch.setattr(configs, "load_example_monitors", True)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/example_monitors/internal")
    monkeypatch.setattr(configs, "example_monitors_path", "tests/example_monitors/others")

    monkeypatch.setattr(registry, "is_monitor_registered", lambda monitor_id: False)

    # Run the controller for a while then stop it
    await monitors_loader._register_monitors()
    await monitors_loader._load_monitors(None)

    controller_task = asyncio.create_task(controller.run())
    await asyncio.sleep(0.2)
    controller_task.cancel()

    assert_message_in_log(caplog, "is not registered, skipping", count=3)


async def test_run_error(caplog, monkeypatch, clear_queue, clear_database):
    """'run' should handle errors and don't break the loop if they happen"""
    monkeypatch.setattr(configs, "load_example_monitors", False)
    monkeypatch.setattr(configs, "internal_monitors_path", "tests/example_monitors/internal")
    monkeypatch.setattr(configs, "example_monitors_path", "tests/example_monitors/others")

    def error(*args):
        raise ValueError("Not able to get the monitors")

    monkeypatch.setattr(controller, "_run_task", error)

    # Run the controller for a while then stop it
    await monitors_loader._register_monitors()
    controller_task = asyncio.create_task(controller.run())
    await monitors_loader._load_monitors(None)
    await asyncio.sleep(0.3)

    assert_message_in_log(caplog, "ValueError: Not able to get the monitors")
    assert_message_in_log(caplog, "Exception caught successfully, going on")
    assert not controller_task.done()

    app.stop()
    await controller_task

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import components.executor.executor as executor
import message_queue as message_queue
import registry as registry
import utils.app as app
import utils.time as time_utils
from configs import configs
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "started_at, last_message_at, expected_result",
    [
        (
            datetime(2024, 1, 1, 12, 34, 0, tzinfo=timezone.utc),
            None,
            ({}, []),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            None,
            (
                {"last_message_at": None},
                ["no_recent_messages"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 33, 1, tzinfo=timezone.utc),
            (
                {"last_message_at": "2024-01-01T12:33:01.000+00:00"},
                [],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            datetime(2024, 1, 1, 12, 20, 3, tzinfo=timezone.utc),
            (
                {"last_message_at": "2024-01-01T12:20:03.000+00:00"},
                ["no_recent_messages"],
            ),
        ),
    ],
)
async def test_diagnostics(monkeypatch, started_at, last_message_at, expected_result):
    """'diagnostics' should return the status and issues for the executor, based on it's
    internal variables"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(executor, "started_at", started_at, raising=False)
    monkeypatch.setattr(executor, "last_message_at", last_message_at, raising=False)

    result = await executor.diagnostics()
    assert result == expected_result


async def test_run(monkeypatch, clear_queue):
    """Integration test of the 'run' method. It should wait for messages and process them using the
    runners"""
    monkeypatch.setattr(configs, "executor_concurrency", 5)
    monkeypatch.setattr(executor, "TASKS_FINISH_CHECK_TIME", 0.01)

    registry.monitors_ready.set()

    event = asyncio.Event()

    async def wait(message):
        await event.wait()

    monkeypatch.setitem(executor.Runner._handlers, "test", wait)

    executor_task = asyncio.create_task(executor.run())

    for i in range(6):
        assert len(event._waiters) == i
        await message_queue.send_message("test", {"test": "aaa"})
        await asyncio.sleep(0.1)

    # The semaphore should allow only 5 tasks to run at the same time, even though there're 6
    # messages in the queue
    assert len(event._waiters) == 5

    # The executor should wait for all tasks to finish when the application is stopping
    app.stop()
    stop_task = asyncio.create_task(asyncio.wait_for(executor_task, timeout=0.5))
    await asyncio.sleep(0.1)
    assert not stop_task.done()

    event.set()

    await asyncio.sleep(0.1)
    assert stop_task.done()
    await stop_task


async def test_run_current_task_error(caplog, monkeypatch):
    """'run' should log an error if it can't get the current task and finish the execution"""
    monkeypatch.setattr(asyncio, "current_task", lambda: None)

    await asyncio.wait_for(executor.run(), timeout=0.1)
    assert_message_in_log(caplog, "Could not get the current asyncio task, finishing")


async def test_run_no_messages(mocker, monkeypatch, clear_queue):
    """'run' should sleep for the configured time when there are no messages in the queue"""
    monkeypatch.setattr(executor, "TASKS_FINISH_CHECK_TIME", 0.01)
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.05,
    )
    monkeypatch.setattr(configs, "executor_sleep", 0.135)

    sleep_spy: AsyncMock = mocker.spy(app, "sleep")

    registry.monitors_ready.set()

    executor_task = asyncio.create_task(executor.run())

    await asyncio.sleep(0.15)
    assert not executor_task.done()

    assert sleep_spy.await_count == 1
    assert sleep_spy.await_args_list == [((0.135,),)]

    await asyncio.sleep(0.15)
    assert not executor_task.done()

    assert sleep_spy.await_count == 2
    assert sleep_spy.await_args_list == [((0.135,),), ((0.135,),)]

    app.stop()

    await asyncio.wait_for(executor_task, timeout=0.5)


async def test_run_error(caplog, monkeypatch, clear_queue):
    """'run' should log exceptions that might occur during the execution without breaking the
    loop"""
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.2,
    )
    monkeypatch.setattr(executor, "TASKS_FINISH_CHECK_TIME", 0.01)

    registry.monitors_ready.set()

    async def error(message):
        raise ValueError("Something went wrong")

    monkeypatch.setitem(executor.Runner._handlers, "test", error)

    executor_task = asyncio.create_task(executor.run())

    await message_queue.send_message("test", {"test": "aaa"})
    await asyncio.sleep(0.1)

    assert_message_in_log(caplog, "ValueError: Something went wrong")
    assert_message_in_log(caplog, "Exception caught successfully, going on")

    await asyncio.sleep(0.1)

    assert not executor_task.done()

    app.stop()

    await asyncio.wait_for(executor_task, timeout=0.5)

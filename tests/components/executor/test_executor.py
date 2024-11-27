import asyncio
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

import src.components.executor.executor as executor
import src.components.executor.monitor_handler as monitor_handler
import src.components.executor.reaction_handler as reaction_handler
import src.components.executor.request_handler as request_handler
import src.queue as queue
import src.registry as registry
import src.utils.app as app
import src.utils.time as time_utils
from src.base_exception import BaseSentinelaException
from src.configs import configs
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "started_at, executors, last_message_at, expected_result",
    [
        (
            datetime(2024, 1, 1, 12, 34, 0, tzinfo=timezone.utc),
            list(range(configs.executor_concurrency)),
            None,
            ({"executors_count": configs.executor_concurrency}, []),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            [],
            None,
            (
                {"executors_count": 0, "last_message_at": None},
                ["degraded_internal_executors", "no_recent_messages"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            list(range(configs.executor_concurrency - 1)),
            datetime(2024, 1, 1, 12, 33, 1, tzinfo=timezone.utc),
            (
                {
                    "executors_count": configs.executor_concurrency - 1,
                    "last_message_at": "2024-01-01T12:33:01.000+00:00",
                },
                ["degraded_internal_executors"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            list(range(configs.executor_concurrency)),
            datetime(2024, 1, 1, 12, 20, 3, tzinfo=timezone.utc),
            (
                {
                    "executors_count": configs.executor_concurrency,
                    "last_message_at": "2024-01-01T12:20:03.000+00:00",
                },
                ["no_recent_messages"],
            ),
        ),
        (
            datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc),
            list(range(configs.executor_concurrency)),
            datetime(2024, 1, 1, 12, 32, 4, tzinfo=timezone.utc),
            (
                {
                    "executors_count": configs.executor_concurrency,
                    "last_message_at": "2024-01-01T12:32:04.000+00:00",
                },
                [],
            ),
        ),
    ],
)
async def test_diagnostics(monkeypatch, started_at, executors, last_message_at, expected_result):
    """'diagnostics' should return the status and issues for the executor, based on it's
    internal variables"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(executor, "started_at", started_at, raising=False)
    monkeypatch.setattr(executor, "executors", executors, raising=False)
    monkeypatch.setattr(executor, "last_message_at", last_message_at, raising=False)

    result = await executor.diagnostics()
    assert result == expected_result


async def test_change_visibility_loop(mocker, monkeypatch, clear_queue):
    """'_change_visibility_loop' should change a message's visibility recurrently until cancelled"""
    monkeypatch.setattr(configs, "queue_visibility_time", 0.2)
    change_visibility_spy: MagicMock = mocker.spy(queue, "change_visibility")

    message = queue.Message(json.dumps({"type": "type", "payload": "payload"}))

    task = asyncio.create_task(executor._change_visibility_loop(message))
    await asyncio.sleep(1.0)
    task.cancel()

    await asyncio.sleep(0.1)

    assert task.done()

    assert change_visibility_spy.call_count == 5
    assert change_visibility_spy.call_args_list == [((message,),)] * 5


async def test_executor_get_message_no_message(monkeypatch, clear_queue):
    """'Executor.get_message' should try to get a message from the queue and, if the timeout is
    reached, should return 'None' without updating the 'last_message_at' variable"""
    monkeypatch.setattr(configs, "queue_wait_message_time", 1)
    monkeypatch.setattr(executor, "last_message_at", None, raising=False)

    ex = executor.Executor(1)

    start_time = time.perf_counter()
    result = await ex.get_message()
    end_time = time.perf_counter()

    assert result is None

    assert executor.last_message_at is None

    total_time = end_time - start_time
    assert total_time > 1 - 0.001
    assert total_time < 1 + 0.005


async def test_executor_get_message_with_message(monkeypatch, clear_queue):
    """'Executor.get_message' should try to get a message from the queue and, if successful, update
    the 'last_message_at' variable with the current time"""
    monkeypatch.setattr(configs, "queue_wait_message_time", 5)
    monkeypatch.setattr(executor, "last_message_at", None, raising=False)

    ex = executor.Executor(1)

    start_time = time.perf_counter()
    task = asyncio.create_task(ex.get_message())
    await asyncio.sleep(0.5)
    assert not task.done()
    await queue.send_message("test", {"test": "aaa"})
    result = await task
    end_time = time.perf_counter()

    assert result is not None
    assert result.content == {"type": "test", "payload": {"test": "aaa"}}

    assert time_utils.time_since(executor.last_message_at) < 1

    total_time = end_time - start_time
    assert total_time > 0.5 - 0.001
    assert total_time < 0.5 + 0.005


@pytest.mark.parametrize(
    "message, expected_result",
    [
        (queue.Message(json.dumps({"type": "event"})), reaction_handler.run),
        (queue.Message(json.dumps({"type": "process_monitor"})), monitor_handler.run),
        (queue.Message(json.dumps({"type": "request"})), request_handler.run),
        (queue.Message(json.dumps({"type": "unknown"})), None),
    ],
)
async def test_executor_get_message_handler(caplog, message, expected_result):
    """'Executor.get_message_handler' should return the correct handler for the provided message or
    None if there isn't one"""
    ex = executor.Executor(1)
    result = ex.get_message_handler(message)

    assert result == expected_result

    if result is None:
        assert_message_in_log(caplog, "Didn't find a handler for message '{\"type\": \"unknown\"}'")


async def test_executor_process_message_success(caplog, mocker, monkeypatch):
    """'Executor.process_message' should process the message with the provided handler, changing
    the message visibility in the queue recurrently during it's processing and deleting the message
    from the queue after finished"""
    monkeypatch.setattr(configs, "queue_visibility_time", 0.1)
    change_visibility_spy: MagicMock = mocker.spy(queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(queue, "delete_message")

    async def sleep(message):
        await asyncio.sleep(0.1)

    handler = AsyncMock(side_effect=sleep)
    message = queue.Message(json.dumps({"type": "test", "payload": "payload"}))
    ex = executor.Executor(1)
    ex._current_message_type = "test"

    await ex.process_message(handler, message)

    handler.assert_awaited_once_with(message.content)
    delete_message_spy.assert_called_once_with(message)
    assert_message_not_in_log(caplog, "Exception caught successfully, going on")

    # Assert the message's visibility was changed
    change_visibility_spy.assert_called_once_with(message)

    # Wait enough time for the visibility change task to run if it wasn't stopped
    await asyncio.sleep(0.3)

    # Assert the message's visibility change task stopped after the completion of the process
    change_visibility_spy.assert_called_once_with(message)


async def test_executor_process_message_sentinela_error(caplog, mocker, monkeypatch):
    """'Executor.process_message' should process the message with the provided handler, catching
    Sentinela exceptions that might occur and logging them properly. The message shouldn't be
    deleted from the queue"""
    monkeypatch.setattr(configs, "queue_visibility_time", 0.1)
    change_visibility_spy: MagicMock = mocker.spy(queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(queue, "delete_message")

    class SomeError(BaseSentinelaException):
        pass

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise SomeError("Something went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    message = queue.Message(json.dumps({"type": "test", "payload": "payload"}))
    ex = executor.Executor(1)
    ex._current_message_type = "test"

    await ex.process_message(handler, message)

    handler.assert_awaited_once_with(message.content)
    delete_message_spy.assert_not_called()
    assert_message_in_log(caplog, "SomeError: Something went wrong")

    # Assert the message's visibility was changed
    change_visibility_spy.assert_called_once_with(message)

    # Wait enough time for the visibility change task to run if it wasn't stopped
    await asyncio.sleep(0.3)

    # Assert the message's visibility change task stopped after the completion of the process
    change_visibility_spy.assert_called_once_with(message)


async def test_executor_process_message_error(caplog, mocker, monkeypatch):
    """'Executor.process_message' should process the message with the provided handler, catching
    exceptions that might occur and logging them properly. The message shouldn't be deleted from
    the queue"""
    monkeypatch.setattr(configs, "queue_visibility_time", 0.1)
    change_visibility_spy: MagicMock = mocker.spy(queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(queue, "delete_message")

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise ValueError("Something went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    message = queue.Message(json.dumps({"type": "test", "payload": "payload"}))
    ex = executor.Executor(1)
    ex._current_message_type = "test"

    await ex.process_message(handler, message)

    handler.assert_awaited_once_with(message.content)
    delete_message_spy.assert_not_called()
    assert_message_in_log(caplog, "ValueError: Something went wrong")
    assert_message_in_log(caplog, "Exception caught successfully, going on")

    # Assert the message's visibility was changed
    change_visibility_spy.assert_called_once_with(message)

    # Wait enough time for the visibility change task to run if it wasn't stopped
    await asyncio.sleep(0.3)

    # Assert the message's visibility change task stopped after the completion of the process
    change_visibility_spy.assert_called_once_with(message)


async def test_executor_process_success(caplog, monkeypatch, clear_queue):
    """'Executor.process' should execute the whole message processing procedure correctly,
    identifying the handler and processing the message with it"""
    registry.monitors_ready.set()

    async def sleep(message):
        await asyncio.sleep(0.1)

    handler = AsyncMock(side_effect=sleep)
    monkeypatch.setitem(executor.Executor._handlers, "test", handler)

    await queue.send_message("test", {"test": "aaa"})
    ex = executor.Executor(1)

    start_time = time.perf_counter()
    await ex.process()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.005

    handler.assert_awaited_once_with({"type": "test", "payload": {"test": "aaa"}})
    assert_message_in_log(caplog, 'Got message \'{"type": "test", "payload": {"test": "aaa"}}\'')


async def test_executor_process_monitors_not_ready(monkeypatch, clear_queue):
    """'Executor.process' should wait for the monitors to be ready before processing any message
    and if it times out, it should propagate the exception"""
    monkeypatch.setattr(registry.registry, "MONITORS_READY_TIMEOUT", 0.1)

    registry.monitors_ready.clear()

    ex = executor.Executor(1)

    start_time = time.perf_counter()
    expected_exception = "MonitorsLoadError: Waiting for monitors to be ready timed out"
    with pytest.raises(registry.MonitorsLoadError, match=expected_exception):
        await ex.process()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.005


async def test_executor_process_no_message(monkeypatch, clear_queue):
    """'Executor.process' should execute the whole message processing procedure correctly, doing
    nothing when no message is received"""
    monkeypatch.setattr(configs, "queue_wait_message_time", 0.5)
    monkeypatch.setattr(configs, "executor_sleep", 0.2)
    registry.monitors_ready.set()

    ex = executor.Executor(1)

    start_time = time.perf_counter()
    await ex.process()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.7 - 0.001
    assert total_time < 0.7 + 0.005


async def test_executor_process_no_handler(caplog, clear_queue):
    """'Executor.process' should execute the whole message processing procedure correctly, and
    doing nothing when there isn't a handler for the message"""
    registry.monitors_ready.set()

    await queue.send_message("test", {"test": "aaa"})
    ex = executor.Executor(1)
    ex._current_message_type = "test"

    start_time = time.perf_counter()
    await ex.process()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time < 0.001

    assert_message_in_log(caplog, "Didn't find a handler for message")


async def test_executor_process_error(caplog, monkeypatch, clear_queue):
    """'Executor.process' should execute the whole message processing procedure correctly,
    identifying the handler, processing the message through it and handling possible exceptions"""
    registry.monitors_ready.set()

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise TypeError("Another thing went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    monkeypatch.setitem(executor.Executor._handlers, "test", handler)

    await queue.send_message("test", {"test": "aaa"})
    ex = executor.Executor(1)

    start_time = time.perf_counter()
    await ex.process()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.005

    handler.assert_awaited_once_with({"type": "test", "payload": {"test": "aaa"}})
    assert_message_in_log(caplog, 'Got message \'{"type": "test", "payload": {"test": "aaa"}}\'')
    assert_message_in_log(caplog, "TypeError: Another thing went wrong")
    assert_message_in_log(caplog, "Exception caught successfully, going on")


async def test_executor_run(monkeypatch):
    """'Executor.run' should keep calling the 'process' method recurrently until the app finishes.
    Error handling is done in it's internal calls"""
    registry.monitors_ready.set()

    async def sleep():
        await asyncio.sleep(0.1)

    process_mock = AsyncMock(side_effect=sleep)
    monkeypatch.setattr(executor.Executor, "process", process_mock)

    ex = executor.Executor(1)
    run_task = asyncio.create_task(ex.run())
    await asyncio.sleep(0.5)
    assert not run_task.done()

    app.stop()
    await asyncio.wait_for(run_task, timeout=0.5)

    assert process_mock.call_count == 5


async def test_executor_run_exception(caplog, monkeypatch):
    """'Executor.run' should keep calling the 'process' method recurrently until the app finishes.
    Even though error handling is done in it's internal calls, it should catch any exceptions
    protecting the loop from breaking"""
    registry.monitors_ready.set()

    async def sleep_error():
        await asyncio.sleep(0.1)
        raise TypeError("Another thing went wrong")

    process_mock = AsyncMock(side_effect=sleep_error)
    monkeypatch.setattr(executor.Executor, "process", process_mock)

    ex = executor.Executor(1)
    run_task = asyncio.create_task(ex.run())
    await asyncio.sleep(0.11)
    assert not run_task.done()

    app.stop()
    await asyncio.wait_for(run_task, timeout=0.5)

    assert process_mock.call_count == 2
    assert_message_in_log(caplog, "TypeError: Another thing went wrong", count=2)


async def test_run(monkeypatch):
    """Integration test of the 'run' method. It should start all the executors and start them.
    When the app stops, it should stop automatically"""
    registry.monitors_ready.set()

    async def sleep():
        await asyncio.sleep(0.1)

    process_mock = AsyncMock(side_effect=sleep)
    monkeypatch.setattr(executor.Executor, "process", process_mock)

    # Run the controller for a while then stop it
    executor_task = asyncio.create_task(executor.run())
    await asyncio.sleep(0.3)
    assert not executor_task.done()

    assert all([not ex.task.done() for ex in executor.executors])

    app.stop()
    await asyncio.wait_for(executor_task, timeout=0.5)

    assert all([ex.task.done() for ex in executor.executors])

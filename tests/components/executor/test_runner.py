import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import components.executor.event_handler as event_handler
import components.executor.monitor_handler as monitor_handler
import components.executor.request_handler as request_handler
import components.executor.runner as runner
import message_queue as message_queue
import registry as registry
from base_exception import BaseSentinelaException
from message_queue.internal_queue import InternalMessage
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_change_visibility_loop(mocker, monkeypatch, clear_queue):
    """'_change_visibility_loop' should change a message's visibility recurrently until cancelled"""
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.2,
    )
    change_visibility_spy: MagicMock = mocker.spy(message_queue, "change_visibility")

    message = InternalMessage(json.dumps({"type": "type", "payload": "payload"}))

    task = asyncio.create_task(runner._change_visibility_loop(message))
    await asyncio.sleep(1.0)
    task.cancel()

    await asyncio.sleep(0.1)

    assert task.done()

    assert change_visibility_spy.call_count == 5
    assert change_visibility_spy.call_args_list == [((message,),)] * 5


@pytest.mark.parametrize(
    "message, expected_result",
    [
        (InternalMessage(json.dumps({"type": "event"})), event_handler.run),
        (InternalMessage(json.dumps({"type": "process_monitor"})), monitor_handler.run),
        (InternalMessage(json.dumps({"type": "request"})), request_handler.run),
        (InternalMessage(json.dumps({"type": "unknown"})), None),
    ],
)
async def test_runner_get_message_handler(caplog, message, expected_result):
    """'Runner.get_message_handler' should return the correct handler for the provided message or
    None if there isn't one"""
    runner_instance = runner.Runner(1, message)
    result = runner_instance.get_message_handler()

    assert result == expected_result

    if result is None:
        assert_message_in_log(caplog, 'Didn\'t find a handler for message \'{"type": "unknown"}\'')


async def test_runner_process_message_success(caplog, mocker, monkeypatch):
    """'Runner.process_message' should process the message with the provided handler, changing
    the message visibility in the queue recurrently during it's processing and deleting the message
    from the queue after finished"""
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.1,
    )
    change_visibility_spy: MagicMock = mocker.spy(message_queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(message_queue, "delete_message")

    async def sleep(message):
        await asyncio.sleep(0.1)

    handler = AsyncMock(side_effect=sleep)
    message = InternalMessage(json.dumps({"type": "test", "payload": "payload"}))
    runner_instance = runner.Runner(1, message)

    await runner_instance.process_message(handler)

    handler.assert_awaited_once_with(message.content)
    delete_message_spy.assert_called_once_with(message)
    assert_message_not_in_log(caplog, "Exception caught successfully, going on")

    # Assert the message's visibility was changed
    change_visibility_spy.assert_called_once_with(message)

    # Wait enough time for the visibility change task to run if it wasn't stopped
    await asyncio.sleep(0.3)

    # Assert the message's visibility change task stopped after the completion of the process
    change_visibility_spy.assert_called_once_with(message)


async def test_runner_process_message_sentinela_error(caplog, mocker, monkeypatch):
    """'Runner.process_message' should process the message with the provided handler, catching
    Sentinela exceptions that might occur and logging them properly. The message shouldn't be
    deleted from the queue"""
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.1,
    )
    change_visibility_spy: MagicMock = mocker.spy(message_queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(message_queue, "delete_message")

    class SomeError(BaseSentinelaException):
        pass

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise SomeError("Something went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    message = InternalMessage(json.dumps({"type": "test", "payload": "payload"}))
    runner_instance = runner.Runner(1, message)

    await runner_instance.process_message(handler)

    handler.assert_awaited_once_with(message.content)
    delete_message_spy.assert_not_called()
    assert_message_in_log(caplog, "SomeError: Something went wrong")

    # Assert the message's visibility was changed
    change_visibility_spy.assert_called_once_with(message)

    # Wait enough time for the visibility change task to run if it wasn't stopped
    await asyncio.sleep(0.3)

    # Assert the message's visibility change task stopped after the completion of the process
    change_visibility_spy.assert_called_once_with(message)


async def test_runner_process_message_error(caplog, mocker, monkeypatch):
    """'Runner.process_message' should process the message with the provided handler, catching
    exceptions that might occur and logging them properly. The message shouldn't be deleted from
    the queue"""
    monkeypatch.setattr(
        message_queue.queue._config,  # type: ignore[attr-defined]
        "queue_wait_message_time",
        0.1,
    )
    change_visibility_spy: MagicMock = mocker.spy(message_queue, "change_visibility")
    delete_message_spy: MagicMock = mocker.spy(message_queue, "delete_message")

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise ValueError("Something went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    message = InternalMessage(json.dumps({"type": "test", "payload": "payload"}))
    runner_instance = runner.Runner(1, message)

    await runner_instance.process_message(handler)

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


@pytest.mark.flaky(reruns=2)
async def test_runner_process_success(caplog, monkeypatch):
    """'Runner.process' should execute the whole message processing procedure correctly,
    identifying the handler and processing the message with it. The semaphore should be held during
    the processing"""
    registry.monitors_ready.set()

    async def sleep(message):
        await asyncio.sleep(0.2)

    handler = AsyncMock(side_effect=sleep)
    monkeypatch.setitem(runner.Runner._handlers, "test", handler)

    message = InternalMessage(json.dumps({"type": "test", "payload": {"test": "aaa"}}))
    runner_instance = runner.Runner(1, message)

    semaphore = asyncio.Semaphore(2)
    assert semaphore._value == 2

    start_time = time.perf_counter()
    process_task = asyncio.create_task(runner_instance.process(semaphore))
    await asyncio.sleep(0.05)
    assert semaphore._value == 1
    await process_task
    end_time = time.perf_counter()

    assert semaphore._value == 2

    total_time = end_time - start_time
    assert total_time > 0.2 - 0.001
    assert total_time < 0.2 + 0.01

    handler.assert_awaited_once_with({"type": "test", "payload": {"test": "aaa"}})
    assert_message_in_log(caplog, 'Got message \'{"type": "test", "payload": {"test": "aaa"}}\'')


@pytest.mark.flaky(reruns=2)
async def test_runner_process_monitors_not_ready(caplog, monkeypatch):
    """'Runner.process' should wait for the monitors to be ready before processing any message
    and if it times out, it should log the exception"""
    monkeypatch.setattr(registry.registry, "MONITORS_READY_TIMEOUT", 0.1)

    registry.monitors_ready.clear()

    runner_instance = runner.Runner(1, InternalMessage("{}"))
    semaphore = asyncio.Semaphore(2)

    start_time = time.perf_counter()
    await runner_instance.process(semaphore)
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.01

    assert_message_in_log(caplog, "MonitorsLoadError: Waiting for monitors to be ready timed out")


@pytest.mark.flaky(reruns=2)
async def test_runner_process_no_handler(caplog):
    """'Runner.process' should execute the whole message processing procedure correctly, and
    do nothing when there isn't a handler for the message"""
    registry.monitors_ready.set()

    message = InternalMessage(json.dumps({"type": "test", "payload": {"test": "aaa"}}))
    runner_instance = runner.Runner(1, message)
    semaphore = asyncio.Semaphore(2)

    start_time = time.perf_counter()
    await runner_instance.process(semaphore)
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time < 0.001

    assert_message_in_log(caplog, "Didn't find a handler for message")


@pytest.mark.flaky(reruns=2)
async def test_runner_process_error(caplog, monkeypatch):
    """'Runner.process' should execute the whole message processing procedure correctly,
    identifying the handler, processing the message through it and handling possible exceptions"""
    registry.monitors_ready.set()

    async def sleep_error(message):
        await asyncio.sleep(0.1)
        raise TypeError("Another thing went wrong")

    handler = AsyncMock(side_effect=sleep_error)
    monkeypatch.setitem(runner.Runner._handlers, "test", handler)

    message = InternalMessage(json.dumps({"type": "test", "payload": {"test": "aaa"}}))
    runner_instance = runner.Runner(1, message)
    semaphore = asyncio.Semaphore(2)

    start_time = time.perf_counter()
    await runner_instance.process(semaphore)
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.1 - 0.001
    assert total_time < 0.1 + 0.01

    handler.assert_awaited_once_with({"type": "test", "payload": {"test": "aaa"}})
    assert_message_in_log(caplog, 'Got message \'{"type": "test", "payload": {"test": "aaa"}}\'')
    assert_message_in_log(caplog, "TypeError: Another thing went wrong")
    assert_message_in_log(caplog, "Exception caught successfully, going on")

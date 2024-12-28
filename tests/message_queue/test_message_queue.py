import json
from unittest.mock import AsyncMock

import pytest

import message_queue as message_queue
import message_queue.internal_queue as internal_queue
import message_queue.sqs_queue as sqs_queue

pytestmark = pytest.mark.asyncio(loop_scope="session")


def set_queue_mock(monkeypatch, queue_type, function_mock):
    """Set the right queue mock for the given queue type"""
    if queue_type == "internal":
        monkeypatch.setattr(message_queue, "queue", internal_queue)
    if queue_type == "sqs":
        monkeypatch.setattr(message_queue, "queue", sqs_queue)

    internal_queue_init_mock = AsyncMock()
    sqs_queue_init_mock = AsyncMock()

    monkeypatch.setattr(internal_queue, function_mock, internal_queue_init_mock)
    monkeypatch.setattr(sqs_queue, function_mock, sqs_queue_init_mock)

    return internal_queue_init_mock, sqs_queue_init_mock


@pytest.mark.parametrize("queue_type", ["internal", "sqs"])
async def test_init(monkeypatch, queue_type):
    """'init' should initialize the queue calling the right module"""
    mocks = set_queue_mock(monkeypatch, queue_type, "init")
    internal_queue_init_mock, sqs_queue_init_mock = mocks

    await message_queue.init()

    if queue_type == "internal":
        internal_queue_init_mock.assert_awaited_once()
        sqs_queue_init_mock.assert_not_called()
    elif queue_type == "sqs":
        internal_queue_init_mock.assert_not_called()
        sqs_queue_init_mock.assert_awaited_once()


@pytest.mark.parametrize("queue_type", ["internal", "sqs"])
async def test_send_message(monkeypatch, queue_type):
    """'send_message' should send a message to the queue calling the right module"""
    mocks = set_queue_mock(monkeypatch, queue_type, "send_message")
    internal_queue_send_message_mock, sqs_queue_send_message_mock = mocks

    await message_queue.send_message("type", {"key": "value"})

    if queue_type == "internal":
        internal_queue_send_message_mock.assert_awaited_once_with("type", {"key": "value"})
        sqs_queue_send_message_mock.assert_not_called()
    elif queue_type == "sqs":
        internal_queue_send_message_mock.assert_not_called()
        sqs_queue_send_message_mock.assert_awaited_once_with("type", {"key": "value"})


@pytest.mark.parametrize("queue_type", ["internal", "sqs"])
async def test_get_message(monkeypatch, queue_type):
    """'get_message' should get a message from the queue calling the right module"""
    mocks = set_queue_mock(monkeypatch, queue_type, "get_message")
    internal_queue_get_message_mock, sqs_queue_get_message_mock = mocks

    await message_queue.get_message()

    if queue_type == "internal":
        internal_queue_get_message_mock.assert_awaited_once()
        sqs_queue_get_message_mock.assert_not_called()
    elif queue_type == "sqs":
        internal_queue_get_message_mock.assert_not_called()
        sqs_queue_get_message_mock.assert_awaited_once()


@pytest.mark.parametrize("queue_type", ["internal", "sqs"])
async def test_change_visibility(monkeypatch, queue_type):
    """'change_visibility' should change the visibility of a message calling the right module"""
    mocks = set_queue_mock(monkeypatch, queue_type, "change_visibility")
    internal_queue_change_visibility_mock, sqs_queue_change_visibility_mock = mocks

    message = internal_queue.Message(json.dumps({"type": "test", "payload": {"a": 1}}))

    await message_queue.change_visibility(message)

    if queue_type == "internal":
        internal_queue_change_visibility_mock.assert_awaited_once_with(message)
        sqs_queue_change_visibility_mock.assert_not_called()
    elif queue_type == "sqs":
        internal_queue_change_visibility_mock.assert_not_called()
        sqs_queue_change_visibility_mock.assert_awaited_once_with(message)


@pytest.mark.parametrize("queue_type", ["internal", "sqs"])
async def test_delete_message(monkeypatch, queue_type):
    """'delete_message' should delete a message from the queue calling the right module"""
    mocks = set_queue_mock(monkeypatch, queue_type, "delete_message")
    internal_queue_delete_message_mock, sqs_queue_delete_message_mock = mocks

    message = internal_queue.Message(json.dumps({"type": "test", "payload": {"a": 1}}))

    await message_queue.delete_message(message)

    if queue_type == "internal":
        internal_queue_delete_message_mock.assert_awaited_once_with(message)
        sqs_queue_delete_message_mock.assert_not_called()
    elif queue_type == "sqs":
        internal_queue_delete_message_mock.assert_not_called()
        sqs_queue_delete_message_mock.assert_awaited_once_with(message)

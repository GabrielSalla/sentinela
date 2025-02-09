import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import message_queue as message_queue
import message_queue.internal_queue as internal_queue
from configs import configs

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="function")
def queue_mocks(monkeypatch) -> tuple[type, type]:
    """Set the right queue mock for the given queue type"""

    class InternalQueueMock:
        __init__ = MagicMock(return_value=None)
        queue_wait_message_time = MagicMock()
        init = AsyncMock()
        send_message = AsyncMock()
        get_message = AsyncMock()
        change_visibility = AsyncMock()
        delete_message = AsyncMock()

    class PluginQueueMock:
        __init__ = MagicMock(return_value=None)
        queue_wait_message_time = MagicMock()
        init = AsyncMock()
        send_message = AsyncMock()
        get_message = AsyncMock()
        change_visibility = AsyncMock()
        delete_message = AsyncMock()

    monkeypatch.setattr(message_queue, "InternalQueue", InternalQueueMock)
    monkeypatch.setattr(message_queue, "get_plugin_queue", lambda queue_type: PluginQueueMock)

    return InternalQueueMock, PluginQueueMock


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_init(monkeypatch, queue_mocks, queue_type):
    """'init' should initialize the queue calling the right module"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    await message_queue.init()

    if queue_type == "internal":
        internal_queue_mock.__init__.assert_called_once_with(config=configs.application_queue)
        internal_queue_mock.init.assert_awaited_once()
        plugin_queue_mock.__init__.assert_not_called()
        plugin_queue_mock.init.assert_not_called()
    elif queue_type == "plugin.":
        internal_queue_mock.__init__.assert_not_called()
        internal_queue_mock.init.assert_not_called()
        plugin_queue_mock.__init__.assert_called_once_with(config=configs.application_queue)
        plugin_queue_mock.init.assert_awaited_once()
    else:
        raise Exception("Invalid queue type")


async def test_init_invalid_queue_type(monkeypatch):
    """'init' should raise a ValueError if the queue type is invalid"""
    monkeypatch.setitem(configs.application_queue, "type", "invalid")

    with pytest.raises(ValueError, match="Invalid queue type 'invalid'"):
        await message_queue.init()


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_get_queue_wait_message_time(monkeypatch, queue_mocks, queue_type):
    """'get_queue_wait_message_time' should return the time to wait for a message in the queue"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    await message_queue.init()
    result = message_queue.get_queue_wait_message_time()

    if queue_type == "internal":
        assert result is internal_queue_mock.queue_wait_message_time
    elif queue_type == "plugin.":
        assert result is plugin_queue_mock.queue_wait_message_time
    else:
        raise Exception("Invalid queue type")


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_send_message(monkeypatch, queue_mocks, queue_type):
    """'send_message' should send a message to the queue calling the right module"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    await message_queue.init()
    await message_queue.send_message("type", {"key": "value"})

    if queue_type == "internal":
        internal_queue_mock.send_message.assert_awaited_once_with("type", {"key": "value"})
        plugin_queue_mock.send_message.assert_not_called()
    elif queue_type == "plugin.":
        internal_queue_mock.send_message.assert_not_called()
        plugin_queue_mock.send_message.assert_awaited_once_with("type", {"key": "value"})
    else:
        raise Exception("Invalid queue type")


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_get_message(monkeypatch, queue_mocks, queue_type):
    """'get_message' should get a message from the queue calling the right module"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    await message_queue.init()
    await message_queue.get_message()

    if queue_type == "internal":
        internal_queue_mock.get_message.assert_awaited_once()
        plugin_queue_mock.get_message.assert_not_called()
    elif queue_type == "plugin.":
        internal_queue_mock.get_message.assert_not_called()
        plugin_queue_mock.get_message.assert_awaited_once()
    else:
        raise Exception("Invalid queue type")


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_change_visibility(monkeypatch, queue_mocks, queue_type):
    """'change_visibility' should change the visibility of a message calling the right module"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    message = internal_queue.InternalMessage(json.dumps({"type": "test", "payload": {"a": 1}}))

    await message_queue.init()
    await message_queue.change_visibility(message)

    if queue_type == "internal":
        internal_queue_mock.change_visibility.assert_awaited_once_with(message)
        plugin_queue_mock.change_visibility.assert_not_called()
    elif queue_type == "plugin.":
        internal_queue_mock.change_visibility.assert_not_called()
        plugin_queue_mock.change_visibility.assert_awaited_once_with(message)
    else:
        raise Exception("Invalid queue type")


@pytest.mark.parametrize("queue_type", ["internal", "plugin."])
async def test_delete_message(monkeypatch, queue_mocks, queue_type):
    """'delete_message' should delete a message from the queue calling the right module"""
    monkeypatch.setitem(configs.application_queue, "type", queue_type)

    internal_queue_mock, plugin_queue_mock = queue_mocks

    message = internal_queue.InternalMessage(json.dumps({"type": "test", "payload": {"a": 1}}))

    await message_queue.init()
    await message_queue.delete_message(message)

    if queue_type == "internal":
        internal_queue_mock.delete_message.assert_awaited_once_with(message)
        plugin_queue_mock.delete_message.assert_not_called()
    elif queue_type == "plugin.":
        internal_queue_mock.delete_message.assert_not_called()
        plugin_queue_mock.delete_message.assert_awaited_once_with(message)
    else:
        raise Exception("Invalid queue type")

import time

import pytest
import pytest_asyncio

import message_queue.internal_queue as internal_queue
from configs import configs

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def set_queue(monkeypatch_module):
    monkeypatch_module.setattr(configs, "queue_wait_message_time", 0.5)
    monkeypatch_module.setattr(configs, "queue_visibility_time", 0.5)


@pytest.mark.parametrize(
    "message_type, message_payload",
    [
        ("test", {"a": 1}),
        ("aaa", {"b": 2}),
        ("123456", {"c": 3, "d": 4}),
    ],
)
async def test_send_message(message_type, message_payload):
    """'send_message' should put a message in the queue"""
    queue = internal_queue.InternalQueue()
    await queue.init()

    await queue.send_message(message_type, message_payload)

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": message_type, "payload": message_payload}


@pytest.mark.flaky(reruns=2)
async def test_get_message_timeout():
    """'get_message' should wait for a message and if the timeout is reached, return 'None'"""
    queue = internal_queue.InternalQueue()
    await queue.init()

    start_time = time.perf_counter()
    message = await queue.get_message()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.5 - 0.001
    assert total_time < 0.5 + 0.005
    assert message is None


async def test_change_visibility():
    """'change_visibility' should not do anything"""
    queue = internal_queue.InternalQueue()
    await queue.init()

    await queue.change_visibility(None)


async def test_delete_message():
    """'delete_message' should not do anything"""
    queue = internal_queue.InternalQueue()
    await queue.init()

    await queue.delete_message(None)

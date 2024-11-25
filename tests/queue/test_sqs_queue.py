import asyncio
import time
from unittest.mock import AsyncMock

import botocore.errorfactory
import botocore.exceptions
import pytest
import pytest_asyncio

import src.queue.sqs_queue as sqs_queue
from src.configs import configs

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def set_queue(monkeypatch_module):
    monkeypatch_module.setattr(
        configs,
        "application_queue",
        {
            "type": "sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": "true",
        },
    )
    monkeypatch_module.setattr(configs, "queue_wait_message_time", 1)
    monkeypatch_module.setattr(configs, "queue_visibility_time", 1)

    await sqs_queue.init()


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def clean_queue():
    async with sqs_queue._aws_client() as client:
        await client.purge_queue(QueueUrl=configs.application_queue["url"])


async def delete_queue(queue_url):
    try:
        async with sqs_queue._aws_client() as client:
            await client.delete_queue(QueueUrl=queue_url)
    except botocore.exceptions.ClientError as e:
        assert e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue"


async def test_init_already_exists(mocker):
    """'init' should do nothing if the queue already exists"""
    create_queue_spy: AsyncMock = mocker.spy(sqs_queue, "_create_queue")

    await sqs_queue.init()

    create_queue_spy.assert_not_called()
    create_queue_spy.assert_not_awaited()


async def test_init_queue_not_exists(mocker, monkeypatch):
    """'init' should create the queue if it doesn't exists and if configured to"""
    monkeypatch.setitem(configs.application_queue, "name", "new_queue")
    create_queue_spy: AsyncMock = mocker.spy(sqs_queue, "_create_queue")

    await delete_queue("http://motoserver:5000/123456789012/new_queue")

    await sqs_queue.init()

    create_queue_spy.assert_awaited_once()


async def test_init_queue_not_exists_not_create(mocker, monkeypatch):
    """'init' should raise an error if the queue doesn't exists and it's not configured to create
    it"""
    monkeypatch.setitem(configs.application_queue, "name", "other_queue")
    monkeypatch.setitem(configs.application_queue, "create_queue", False)
    create_queue_spy: AsyncMock = mocker.spy(sqs_queue, "_create_queue")

    await delete_queue("http://motoserver:5000/123456789012/other_queue")

    with pytest.raises(RuntimeError, match="AWS SQS queue must exist"):
        await sqs_queue.init()

    create_queue_spy.assert_not_called()
    create_queue_spy.assert_not_awaited()


@pytest.mark.parametrize(
    "message_type, message_payload",
    [
        ("test", {"a": 1}),
        ("aaa", {"b": 2}),
        ("123456", {"c": 3, "d": 4}),
    ],
)
async def test_send_message_and_get_message(message_type, message_payload):
    """'send_message' should send the message to the queue that can be, later on, consumed
    using 'get_message'"""
    await sqs_queue.send_message(message_type, message_payload)

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": message_type, "payload": message_payload}


@pytest.mark.parametrize(
    "message_type, message_payload",
    [
        ("test", {"a": 1}),
        ("aaa", {"b": 2}),
        ("123456", {"c": 3, "d": 4}),
    ],
)
async def test_send_message_after_get_message(message_type, message_payload):
    """'get_message' should wait for a message and will return it if a message is sent to the
    queue using 'send_message', while it's waiting"""
    get_task = asyncio.create_task(sqs_queue.get_message())

    await asyncio.sleep(0.5)

    assert not get_task.done()
    await sqs_queue.send_message(message_type, message_payload)

    message = await get_task
    assert message is not None
    assert message.content == {"type": message_type, "payload": message_payload}


async def test_get_message_timeout():
    """'get_message' should wait for a message and if the timeout is reached, return 'None'"""
    start_time = time.perf_counter()
    message = await sqs_queue.get_message()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 1 - 0.001
    assert total_time < 1 + 0.5
    assert message is None


async def test_get_message_not_deleted():
    """'get_message' should get a message that was already consumed before, but it was not deleted
    before it's timeout"""
    await sqs_queue.send_message("test", {"a": 1})

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    message = await sqs_queue.get_message()
    assert message is None

    await asyncio.sleep(1)

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}


async def test_change_visibility():
    """'change_visibility' should change the message visibility timeeout, keeping it from
    being consumed again while still not visible"""
    await sqs_queue.send_message("test", {"a": 1})

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    for _ in range(3):
        await sqs_queue.change_visibility(message)
        new_message = await sqs_queue.get_message()
        assert new_message is None

    await asyncio.sleep(1)

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}


async def test_delete_message():
    """'delete_message' should remove the message from the queue permanently"""
    await sqs_queue.send_message("test", {"a": 1})

    message = await sqs_queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    await sqs_queue.delete_message(message)

    await asyncio.sleep(2)

    message = await sqs_queue.get_message()
    assert message is None

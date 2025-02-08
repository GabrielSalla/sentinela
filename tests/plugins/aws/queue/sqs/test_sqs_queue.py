import asyncio
import time
from unittest.mock import AsyncMock

import botocore.errorfactory
import botocore.exceptions
import pytest
import pytest_asyncio

import plugins.aws.client as aws_client
import plugins.aws.queue.sqs as sqs_queue

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def clean_queue() -> None:
    """Clean the queue before each test"""
    aws_client_params = {
        "credential_name": "application",
        "service": "sqs",
        "region_name": "us-east-1",
    }
    try:
        async with aws_client.aws_client(**aws_client_params) as client:
            await client.purge_queue(QueueUrl="http://motoserver:5000/123456789012/app")
    except botocore.exceptions.ClientError as e:
        assert e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue"


async def delete_queue(queue_url: str) -> None:
    """Delete the queue"""
    aws_client_params = {
        "credential_name": "application",
        "service": "sqs",
        "region_name": "us-east-1",
    }
    try:
        async with aws_client.aws_client(**aws_client_params) as client:
            await client.delete_queue(QueueUrl=queue_url)
    except botocore.exceptions.ClientError as e:
        assert e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue"


@pytest.mark.parametrize("queue_wait_message_time", [1, 2, 3, 4, 5])
async def test_queue_wait_message_time(queue_wait_message_time):
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": queue_wait_message_time,
            "queue_visibility_time": 15,
        }
    )
    assert queue.queue_wait_message_time == queue_wait_message_time


async def test_init_already_exists(mocker):
    """'init' should do nothing if the queue already exists"""
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    create_queue_spy: AsyncMock = mocker.spy(sqs_queue.sqs_queue, "_create_queue")

    await queue.init()

    create_queue_spy.assert_not_called()
    create_queue_spy.assert_not_awaited()


async def test_init_queue_not_exists(mocker):
    """'init' should create the queue if it doesn't exists and if configured to"""
    create_queue_spy: AsyncMock = mocker.spy(sqs_queue.sqs_queue, "_create_queue")

    await delete_queue("http://motoserver:5000/123456789012/new_queue")

    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "new_queue",
            "url": "http://motoserver:5000/123456789012/new_queue",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    create_queue_spy.assert_awaited_once()


async def test_init_queue_not_exists_not_create(mocker):
    """'init' should raise an error if the queue doesn't exists and it's not configured to create
    it"""
    create_queue_spy: AsyncMock = mocker.spy(sqs_queue.sqs_queue, "_create_queue")

    await delete_queue("http://motoserver:5000/123456789012/other_queue")

    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "other_queue",
            "url": "http://motoserver:5000/123456789012/other_queue",
            "region": "us-east-1",
            "create_queue": False,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    with pytest.raises(RuntimeError, match="AWS SQS queue must exist"):
        await queue.init()

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
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    await queue.send_message(message_type, message_payload)

    message = await queue.get_message()
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
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    get_task = asyncio.create_task(queue.get_message())

    await asyncio.sleep(0.5)

    assert not get_task.done()
    await queue.send_message(message_type, message_payload)

    message = await get_task
    assert message is not None
    assert message.content == {"type": message_type, "payload": message_payload}


@pytest.mark.flaky(reruns=2)
async def test_get_message_timeout():
    """'get_message' should wait for a message and if the timeout is reached, return 'None'"""
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 1,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    start_time = time.perf_counter()
    message = await queue.get_message()
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 1 - 0.001
    assert total_time < 1 + 0.5
    assert message is None


async def test_get_message_not_deleted():
    """'get_message' should get a message that was already consumed before, but it was not deleted
    before it's timeout"""
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 1,
        }
    )
    await queue.init()

    await queue.send_message("test", {"a": 1})

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    message = await queue.get_message()
    assert message is None

    await asyncio.sleep(1)

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}


async def test_change_visibility():
    """'change_visibility' should change the message visibility timeeout, keeping it from
    being consumed again while still not visible"""
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 1,
        }
    )
    await queue.init()

    await queue.send_message("test", {"a": 1})

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    for _ in range(3):
        await queue.change_visibility(message)
        new_message = await queue.get_message()
        assert new_message is None

    await asyncio.sleep(1)

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}


async def test_delete_message():
    """'delete_message' should remove the message from the queue permanently"""
    queue = sqs_queue.Queue(
        config={
            "type": "plugin.aws.sqs",
            "name": "app",
            "url": "http://motoserver:5000/123456789012/app",
            "region": "us-east-1",
            "create_queue": True,
            "queue_wait_message_time": 2,
            "queue_visibility_time": 15,
        }
    )
    await queue.init()

    await queue.send_message("test", {"a": 1})

    message = await queue.get_message()
    assert message is not None
    assert message.content == {"type": "test", "payload": {"a": 1}}

    await queue.delete_message(message)

    await asyncio.sleep(2)

    message = await queue.get_message()
    assert message is None

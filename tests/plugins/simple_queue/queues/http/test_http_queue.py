import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer

import plugins.simple_queue.queues.http as http_queue

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session")
async def queue_url():
    """Start a local HTTP server for plugin integration tests."""
    state = {"empty": False}
    app = web.Application()

    async def send_message(request):
        """Return a successful send response."""
        return web.json_response({"id": "message-id"}, status=201)

    async def get_message(request):
        """Return a message or an empty response based on test state."""
        if state["empty"]:
            return web.Response(status=204)
        return web.json_response(
            {"id": "message-id", "content": {"type": "test", "payload": {"key": "value"}}}
        )

    async def operation(request):
        """Return a successful queue operation response."""
        return web.Response(status=204)

    app.add_routes(
        [
            web.post("/messages", send_message),
            web.get("/messages", get_message),
            web.post("/messages/{message_id}/visibility", operation),
            web.delete("/messages/{message_id}", operation),
        ]
    )
    server = TestServer(app)
    await server.start_server()
    yield str(server.make_url("/")).rstrip("/"), state
    await server.close()


async def test_queue_wait_message_time(queue_url):
    """'queue_wait_message_time' should return the fixed wait time and normalize trailing slashes"""
    url, _ = queue_url
    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": url})
    assert queue.queue_wait_message_time == 2

    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": f"{url}/"})
    assert queue._url == url


async def test_init(queue_url):
    """'init' should initialize the queue client"""
    url, _ = queue_url
    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": url})
    await queue.init()


async def test_send_message_and_get_message(queue_url):
    """'send_message' should send a message that 'get_message' can receive"""
    url, _ = queue_url
    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": url})
    await queue.send_message("test", {"key": "value"})

    message = await queue.get_message()

    assert message is not None
    assert message.id
    assert message.content == {"type": "test", "payload": {"key": "value"}}


async def test_get_message_empty(queue_url):
    """'get_message' should return None when the HTTP queue has no message"""
    url, state = queue_url
    state["empty"] = True
    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": url})

    assert await queue.get_message() is None


async def test_change_visibility_and_delete_message(queue_url):
    """'change_visibility' and 'delete_message' should update and remove a received message"""
    url, _ = queue_url
    queue = http_queue.Queue(config={"type": "plugin.simple_queue.queues.http", "url": url})
    await queue.send_message("test", {})
    message = await queue.get_message()
    assert message is not None

    await queue.change_visibility(message)
    await queue.delete_message(message)

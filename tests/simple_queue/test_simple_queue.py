import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

import simple_queue.simple_queue as simple_queue

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def client():
    """Start an HTTP client connected to a fresh queue application."""
    client = TestClient(TestServer(simple_queue.create_app()))
    await client.start_server()
    yield client
    await client.close()


async def test_send_message(client):
    """'send_message' should enqueue a message that 'get_message' can receive"""
    response = await client.post("/messages", json={"type": "test", "payload": {"key": "value"}})

    assert response.status == 201
    body = await response.json()
    assert body["id"]

    response = await client.get("/messages")
    assert response.status == 200
    assert (await response.json()) == {
        "id": body["id"],
        "content": {"type": "test", "payload": {"key": "value"}},
    }


async def test_status(client):
    """'status' should report a successful queue service response"""
    response = await client.get("/status")

    assert response.status == 200


@pytest.mark.parametrize(
    "body, error",
    [
        (None, "'type' must be a string"),
        ({"type": 1, "payload": {}}, "'type' must be a string"),
        ({"type": "test", "payload": []}, "'payload' must be an object"),
    ],
)
async def test_send_message_invalid_body(client, body, error):
    """'send_message' should reject malformed message bodies"""
    response = await client.post("/messages", json=body)

    assert response.status == 400
    assert (await response.json())["error"] == error


async def test_get_message_timeout(client, monkeypatch):
    """'get_message' should return no message immediately when wait time is zero"""
    monkeypatch.setattr(simple_queue, "WAIT_MESSAGE_TIME", 0)

    response = await client.get("/messages")

    assert response.status == 204


async def test_get_message_timeout_after_waiting(client, monkeypatch):
    """'get_message' should return no message after the configured wait time"""
    monkeypatch.setattr(simple_queue, "WAIT_MESSAGE_TIME", 0.01)

    response = await client.get("/messages")

    assert response.status == 204


async def test_get_next_message_deadline(monkeypatch):
    """'get_next_message' should stop polling when the message deadline has elapsed"""
    times = iter([0, 0, 1, 1])
    monkeypatch.setattr(simple_queue, "monotonic", lambda: next(times))
    monkeypatch.setattr(simple_queue, "WAIT_MESSAGE_TIME", 0.1)
    simple_queue.create_app()

    assert await simple_queue._get_next_message() is None


async def test_send_message_invalid_json(client):
    """'send_message' should reject requests containing invalid JSON"""
    response = await client.post("/messages", data="not json")

    assert response.status == 400
    assert (await response.json())["error"] == "'type' must be a string"


async def test_change_visibility(client, monkeypatch):
    """'change_visibility' should renew visibility and 'delete_message' should remove the message"""
    monkeypatch.setattr(simple_queue, "VISIBILITY_TIME", 10)
    await client.post("/messages", json={"type": "test", "payload": {}})
    response = await client.get("/messages")
    message = await response.json()

    response = await client.post(f"/messages/{message['id']}/visibility")
    assert response.status == 204

    response = await client.delete(f"/messages/{message['id']}")
    assert response.status == 204


@pytest.mark.parametrize("method, path", [("post", "visibility"), ("delete", "")])
async def test_message_operation_not_found(client, method, path):
    """Message operations should return not found for unknown messages"""
    url = f"/messages/unknown/{path}" if path else "/messages/unknown"
    response = await getattr(client, method)(url)

    assert response.status == 404
    assert (await response.json())["error"] == "Message not found"


async def test_message_is_requeued_after_visibility_expires(client, monkeypatch):
    """'get_message' should requeue a message after its visibility lease expires"""
    monkeypatch.setattr(simple_queue, "VISIBILITY_TIME", 0)
    monkeypatch.setattr(simple_queue, "WAIT_MESSAGE_TIME", 0.1)
    await client.post("/messages", json={"type": "test", "payload": {}})

    first_response = await client.get("/messages")
    first_message = await first_response.json()
    second_response = await client.get("/messages")

    assert second_response.status == 200
    second_message = await second_response.json()
    assert second_message["id"] != first_message["id"]
    assert second_message["content"] == first_message["content"]


async def test_message_operations_reject_stale_delivery(client, monkeypatch):
    """Stale delivery tokens should not affect a requeued message"""
    monkeypatch.setattr(simple_queue, "VISIBILITY_TIME", 0)
    await client.post("/messages", json={"type": "test", "payload": {}})

    first_response = await client.get("/messages")
    first_message = await first_response.json()

    response = await client.delete(f"/messages/{first_message['id']}")
    assert response.status == 404

    monkeypatch.setattr(simple_queue, "VISIBILITY_TIME", 10)
    second_response = await client.get("/messages")
    second_message = await second_response.json()

    response = await client.post(f"/messages/{first_message['id']}/visibility")
    assert response.status == 404
    response = await client.delete(f"/messages/{first_message['id']}")
    assert response.status == 404

    response = await client.delete(f"/messages/{second_message['id']}")
    assert response.status == 204


async def test_message_is_requeued_while_waiting(client, monkeypatch):
    """'get_message' should requeue an expired message during a long-poll request"""
    monkeypatch.setattr(simple_queue, "VISIBILITY_TIME", 0.001)
    monkeypatch.setattr(simple_queue, "WAIT_MESSAGE_TIME", 0.1)
    await client.post("/messages", json={"type": "test", "payload": {}})
    first_response = await client.get("/messages")
    first_message = await first_response.json()

    second_response = await client.get("/messages")

    assert second_response.status == 200
    second_message = await second_response.json()
    assert second_message["id"] != first_message["id"]
    assert second_message["content"] == first_message["content"]


async def test_main(mocker):
    """'main' should start the server on the configured host and port"""
    run_app_mock = mocker.patch.object(simple_queue.web, "run_app")

    simple_queue.main()

    run_app_mock.assert_called_once()
    assert run_app_mock.call_args.kwargs == {"host": "0.0.0.0", "port": 5000}

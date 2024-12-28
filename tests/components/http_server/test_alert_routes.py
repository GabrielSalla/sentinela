import json

import aiohttp
import pytest
import pytest_asyncio

import components.controller.controller as controller
import components.http_server as http_server
import message_queue as message_queue
from models import Alert, Monitor

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/alert"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    controller.running = True
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_alert_acknowledge(clear_queue, sample_monitor: Monitor):
    """The 'alert acknowledge' route should queue an request to acknowledge the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    assert message_queue.internal_queue._queue.empty()

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/acknowledge") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_acknowledge",
                "target_id": alert.id,
            }

    queue_items = []
    while not message_queue.internal_queue._queue.empty():
        queue_items.append(message_queue.internal_queue._queue.get_nowait())

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_acknowledge",
            "target_id": alert.id,
        },
    }


async def test_alert_acknowledge_alert_not_found(clear_queue):
    """The 'alert acknowledge' route should return and 404 error if the provided alert was not
    found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/acknowledge") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    assert message_queue.internal_queue._queue.empty()


async def test_alert_lock(clear_queue, sample_monitor: Monitor):
    """The 'alert lock' route should queue an request to lock the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    assert message_queue.internal_queue._queue.empty()

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/lock") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_lock",
                "target_id": alert.id,
            }

    queue_items = []
    while not message_queue.internal_queue._queue.empty():
        queue_items.append(message_queue.internal_queue._queue.get_nowait())

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_lock",
            "target_id": alert.id,
        },
    }


async def test_alert_lock_alert_not_found(clear_queue):
    """The 'alert lock' route should return and 404 error if the provided alert was not found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/lock") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    assert message_queue.internal_queue._queue.empty()


async def test_alert_solve(clear_queue, sample_monitor: Monitor):
    """The 'alert solve' route should queue an request to solve the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    assert message_queue.internal_queue._queue.empty()

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/solve") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_solve",
                "target_id": alert.id,
            }

    queue_items = []
    while not message_queue.internal_queue._queue.empty():
        queue_items.append(message_queue.internal_queue._queue.get_nowait())

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_solve",
            "target_id": alert.id,
        },
    }


async def test_alert_solve_alert_not_found(clear_queue):
    """The 'alert solve' route should return and 404 error if the provided alert was not
    found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/solve") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    assert message_queue.internal_queue._queue.empty()

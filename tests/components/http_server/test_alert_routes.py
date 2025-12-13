import json

import aiohttp
import pytest
import pytest_asyncio

import components.controller.controller as controller
import components.http_server as http_server
from models import Alert, Issue, Monitor
from tests.message_queue.utils import get_queue_items
from utils.time import localize

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/alert"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    controller.running = True
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_get_alert(sample_monitor: Monitor):
    alerts = await Alert.create_batch(
        [
            Alert(
                monitor_id=sample_monitor.id,
                priority=1,
            ),
            Alert(
                monitor_id=sample_monitor.id,
                priority=2,
            ),
        ]
    )

    for alert in alerts:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL + f"/{alert.id}") as response:
                assert await response.json() == {
                    "id": alert.id,
                    "status": alert.status.value,
                    "acknowledged": alert.acknowledged,
                    "locked": alert.locked,
                    "priority": alert.priority,
                    "acknowledge_priority": alert.acknowledge_priority,
                    "can_acknowledge": alert.can_acknowledge,
                    "can_lock": alert.can_lock,
                    "can_solve": alert.can_solve,
                    "created_at": localize(alert.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                }


async def test_get_alert_not_found(sample_monitor: Monitor):
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/0") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}


@pytest.mark.parametrize("issues_count", range(4))
async def test_list_alert_active_issues(sample_monitor: Monitor, issues_count):
    alert = await Alert.create(monitor_id=sample_monitor.id)

    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                alert_id=alert.id,
            )
            for _ in range(issues_count)
        ]
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + f"/{alert.id}/issues") as response:
            assert await response.json() == [
                {
                    "id": issue.id,
                    "status": issue.status.value,
                    "model_id": issue.model_id,
                    "data": issue.data,
                    "created_at": localize(issue.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                }
                for issue in issues
            ]


async def test_list_alert_active_issues_alert_not_found():
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/0/issues") as response:
            assert await response.json() == []


async def test_alert_acknowledge(clear_queue, sample_monitor: Monitor):
    """The 'alert acknowledge' route should queue an request to acknowledge the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    queue_items = get_queue_items()
    assert len(queue_items) == 0

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/acknowledge") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_acknowledge",
                "target_id": alert.id,
            }

    queue_items = get_queue_items()

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_acknowledge",
            "params": {"target_id": alert.id},
        },
    }


async def test_alert_acknowledge_alert_not_found(clear_queue):
    """The 'alert acknowledge' route should return and 404 error if the provided alert was not
    found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/acknowledge") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    queue_items = get_queue_items()
    assert len(queue_items) == 0


async def test_alert_lock(clear_queue, sample_monitor: Monitor):
    """The 'alert lock' route should queue an request to lock the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    queue_items = get_queue_items()
    assert len(queue_items) == 0

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/lock") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_lock",
                "target_id": alert.id,
            }

    queue_items = get_queue_items()

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_lock",
            "params": {"target_id": alert.id},
        },
    }


async def test_alert_lock_alert_not_found(clear_queue):
    """The 'alert lock' route should return and 404 error if the provided alert was not found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/lock") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    queue_items = get_queue_items()
    assert len(queue_items) == 0


async def test_alert_solve(clear_queue, sample_monitor: Monitor):
    """The 'alert solve' route should queue an request to solve the provided alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    queue_items = get_queue_items()
    assert len(queue_items) == 0

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{alert.id}/solve") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "alert_solve",
                "target_id": alert.id,
            }

    queue_items = get_queue_items()

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "alert_solve",
            "params": {"target_id": alert.id},
        },
    }


async def test_alert_solve_alert_not_found(clear_queue):
    """The 'alert solve' route should return and 404 error if the provided alert was not
    found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/solve") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "alert '0' not found"}

    queue_items = get_queue_items()
    assert len(queue_items) == 0

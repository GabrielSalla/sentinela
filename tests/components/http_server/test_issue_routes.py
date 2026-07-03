import json

import aiohttp
import pytest
import pytest_asyncio

import components.controller.controller as controller
import components.http_server as http_server
from models import Issue, Monitor
from tests.message_queue.utils import get_queue_items

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/issue"
INT_PARSING_ERROR = "Input should be a valid integer, unable to parse string as an integer"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    controller.running = True
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_issue_drop(clear_queue, sample_monitor: Monitor):
    """The 'issue drop' route should queue an request to drop the provided issue"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )

    queue_items = get_queue_items()
    assert len(queue_items) == 0

    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + f"/{issue.id}/drop") as response:
            assert await response.json() == {
                "status": "request_queued",
                "action": "issue_drop",
                "target_id": issue.id,
            }

    queue_items = get_queue_items()

    assert len(queue_items) == 1
    assert json.loads(queue_items[0]) == {
        "type": "request",
        "payload": {
            "action": "issue_drop",
            "params": {"target_id": issue.id},
        },
    }


async def test_issue_drop_issue_not_found(clear_queue):
    """The 'issue drop' route should return and 404 error if the provided issue was not found"""
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/0/drop") as response:
            assert response.status == 404
            assert await response.json() == {"status": "error", "message": "Issue 0 not found"}

    queue_items = get_queue_items()
    assert len(queue_items) == 0


async def test_issue_drop_invalid_issue_id(clear_queue):
    async with aiohttp.ClientSession() as session:
        async with session.post(BASE_URL + "/invalid/drop") as response:
            assert response.status == 400
            assert await response.json() == {
                "status": "error",
                "message": "Invalid request data",
                "errors": [f"issue_id: {INT_PARSING_ERROR}"],
            }

    queue_items = get_queue_items()
    assert len(queue_items) == 0

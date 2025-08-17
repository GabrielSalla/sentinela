import aiohttp
import pytest
import pytest_asyncio
from prometheus_client import parser

import components.controller.controller as controller
import components.executor.executor as executor
import components.http_server as http_server

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    await http_server.init()
    yield
    await http_server.wait_stop()


async def restart_http_server(controller_enabled: bool):
    """Restart the HTTP server"""
    await http_server.wait_stop()
    await http_server.init(controller_enabled=controller_enabled)


@pytest.fixture(scope="function", autouse=True)
def reset_components(setup_http_server):
    """Reset the running flags for the 'controller' and 'executor'"""
    controller.running = False
    executor.running = False


@pytest.mark.parametrize(
    "controller_running, executor_running",
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
async def test_status(controller_running, executor_running):
    """The 'status' route should return the status of the application and it's components"""
    controller.running = controller_running
    executor.running = executor_running

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/status") as response:
            response_data = await response.json()

    assert "status" in response_data
    assert "monitors_loaded" in response_data

    if controller_running:
        assert "controller" in response_data["components"]
        assert "status" in response_data["components"]["controller"]
        assert "issues" in response_data["components"]["controller"]

    if executor_running:
        assert "executor" in response_data["components"]
        assert "status" in response_data["components"]["executor"]
        assert "issues" in response_data["components"]["executor"]


async def test_status_controller_ok(monkeypatch):
    """The 'status' route should return the correct information for the controller when it doesn't
    have errors"""
    controller.running = True

    async def diagnostics():
        return ["a", "bc", "def"], []

    monkeypatch.setattr(controller, "diagnostics", diagnostics)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/status") as response:
            response_data = await response.json()

    assert response_data["status"] == "ok"
    assert response_data["components"]["controller"] == {
        "status": ["a", "bc", "def"],
        "issues": [],
    }


async def test_status_controller_degraded(monkeypatch):
    """The 'status' route should return the correct information for the controller when it's
    degraded"""
    controller.running = True

    async def diagnostics():
        return ["a", "bc", "def"], ["1", "23", "456"]

    monkeypatch.setattr(controller, "diagnostics", diagnostics)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/status") as response:
            response_data = await response.json()

    assert response_data["status"] == "degraded"
    assert response_data["components"]["controller"] == {
        "status": ["a", "bc", "def"],
        "issues": ["1", "23", "456"],
    }


async def test_status_executor_ok(monkeypatch):
    """The 'status' route should return the correct information for the executor when it doesn't
    have errors"""
    executor.running = True

    async def diagnostics():
        return ["a", "bc", "def"], []

    monkeypatch.setattr(executor, "diagnostics", diagnostics)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/status") as response:
            response_data = await response.json()

    assert response_data["status"] == "ok"
    assert response_data["components"]["executor"] == {
        "status": ["a", "bc", "def"],
        "issues": [],
    }


async def test_status_executor_degraded(monkeypatch):
    """The 'status' route should return the correct information for the executor when it's
    degraded"""
    executor.running = True

    async def diagnostics():
        return ["a", "bc", "def"], ["1", "23", "456"]

    monkeypatch.setattr(executor, "diagnostics", diagnostics)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/status") as response:
            response_data = await response.json()

    assert response_data["status"] == "degraded"
    assert response_data["components"]["executor"] == {
        "status": ["a", "bc", "def"],
        "issues": ["1", "23", "456"],
    }


async def test_metrics():
    """The 'metrics' route should return metrics from Prometheus"""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/metrics") as response:
            response_data = await response.text()

    for family in parser.text_string_to_metric_families(response_data):
        for sample in family.samples:
            assert list(sample)


async def test_init_controller_enabled():
    """'init' should include the alerts, issues and monitor routes and the dashboard if the
    controller is enabled"""
    await restart_http_server(controller_enabled=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/monitor/list") as response:
            assert response.status == 200
            result = await response.json()
            assert isinstance(result, list)


async def test_init_controller_disabled():
    """'init' should not include the alerts, issues and monitor routes and the dashboard if the
    controller is not enabled"""
    await restart_http_server(controller_enabled=False)

    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL + "/monitor/list") as response:
            assert response.status == 404
            assert await response.text() == "404: Not Found"

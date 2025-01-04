from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_asyncio

import components.controller.controller as controller
import components.http_server as http_server
import external_requests as external_requests
from models import CodeModule, Monitor

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/monitor"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    controller.running = True
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_monitor_disable(mocker, clear_database, sample_monitor: Monitor):
    """The 'monitor disable' route should disable a monitor"""
    monitor_disable_spy: AsyncMock = mocker.spy(external_requests, "disable_monitor")

    assert sample_monitor.enabled

    url = BASE_URL + f"/{sample_monitor.name}/disable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_disable_spy.assert_awaited_once_with(sample_monitor.name)
    assert response_data == {
        "status": "monitor_disabled",
        "monitor_name": sample_monitor.name,
    }

    await sample_monitor.refresh()
    assert not sample_monitor.enabled


async def test_monitor_disable_not_found(mocker, clear_database):
    """The 'monitor disable' route should return an error if the monitor is not found"""
    monitor_disable_spy: AsyncMock = mocker.spy(external_requests, "disable_monitor")

    url = BASE_URL + "/not_found/disable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_disable_spy.assert_awaited_once_with("not_found")
    assert response_data == {
        "status": "error",
        "error": "Monitor 'not_found' not found",
    }


async def test_monitor_disable_error(mocker, clear_database):
    """The 'monitor disable' route should return an error if an exception is raised"""
    monitor_disable_spy: AsyncMock = mocker.spy(external_requests, "disable_monitor")
    monitor_disable_spy.side_effect = Exception("Something went wrong")

    url = BASE_URL + "/error/disable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_disable_spy.assert_awaited_once_with("error")
    assert response_data == {
        "status": "error",
        "error": "Something went wrong",
    }


async def test_monitor_enable(mocker, clear_database, sample_monitor: Monitor):
    """The 'monitor enable' route should enable a monitor"""
    monitor_enable_spy: AsyncMock = mocker.spy(external_requests, "enable_monitor")

    await sample_monitor.set_enabled(False)
    assert not sample_monitor.enabled

    url = BASE_URL + f"/{sample_monitor.name}/enable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_enable_spy.assert_awaited_once_with(sample_monitor.name)
    assert response_data == {
        "status": "monitor_enabled",
        "monitor_name": sample_monitor.name,
    }

    await sample_monitor.refresh()
    assert sample_monitor.enabled


async def test_monitor_enable_not_found(mocker, clear_database):
    """The 'monitor enable' route should return an error if the monitor is not found"""
    monitor_enable_spy: AsyncMock = mocker.spy(external_requests, "enable_monitor")

    url = BASE_URL + "/not_found/enable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_enable_spy.assert_awaited_once_with("not_found")
    assert response_data == {
        "status": "error",
        "error": "Monitor 'not_found' not found",
    }


async def test_monitor_enable_error(mocker, clear_database):
    """The 'monitor enable' route should return an error if an exception is raised"""
    monitor_enable_spy: AsyncMock = mocker.spy(external_requests, "enable_monitor")
    monitor_enable_spy.side_effect = Exception("Something went wrong")

    url = BASE_URL + "/error/enable"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            response_data = await response.json()

    monitor_enable_spy.assert_awaited_once_with("error")
    assert response_data == {
        "status": "error",
        "error": "Something went wrong",
    }


@pytest.mark.parametrize("monitor_name", [
    "test_monitor_register",
    "test_monitor_register_different_name",
    "test.monitor.register.name.with.dots",
])
async def test_monitor_register(mocker, clear_database, monitor_name):
    """The 'monitor register' route should register a new monitor with the provided module code if
    it doesn't exists. The monitor name should replace any dots with underscores"""
    monitor_register_spy: AsyncMock = mocker.spy(external_requests, "monitor_register")

    monitor = await Monitor.get(Monitor.name == monitor_name)
    assert monitor is None

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    request_payload = {"monitor_code": monitor_code}

    url = BASE_URL + f"/register/{monitor_name}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            response_data = await response.json()

    cleaned_monitor_name = monitor_name.replace(".", "_")
    monitor_register_spy.assert_awaited_once_with(cleaned_monitor_name, monitor_code, {})

    monitor = await Monitor.get(Monitor.name == cleaned_monitor_name)
    assert monitor is not None
    assert response_data == {
        "status": "monitor_registered",
        "monitor_id": monitor.id,
    }

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None
    assert code_module.code == monitor_code


async def test_monitor_register_batch(mocker, clear_database):
    """The 'monitor register' route should register a batch of monitors when multiple requests are
    received in a small time frame"""
    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    request_payload = {"monitor_code": monitor_code}

    for i in range(50):
        monitor_name = f"register_batch_{i}"
        monitor = await Monitor.get(Monitor.name == monitor_name)
        assert monitor is None

        url = BASE_URL + f"/register/{monitor_name}"
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_payload) as response:
                response_data = await response.json()

        monitor = await Monitor.get(Monitor.name == monitor_name)
        assert monitor is not None
        assert response_data == {
            "status": "monitor_registered",
            "monitor_id": monitor.id,
        }


async def test_monitor_register_additional_files(mocker, clear_database):
    """The 'monitor register' route should register a new monitor with the provided module code and
    additional files if it not exists"""
    monitor_register_spy: AsyncMock = mocker.spy(external_requests, "monitor_register")

    monitor_name = "test_monitor_register_additional_files"
    monitor = await Monitor.get(Monitor.name == monitor_name)
    assert monitor is None

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    request_payload = {
        "monitor_code": monitor_code,
        "additional_files": {"file.sql": "SELECT 1;"},
    }

    url = BASE_URL + f"/register/{monitor_name}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            response_data = await response.json()

    monitor_register_spy.assert_awaited_once_with(
        monitor_name, monitor_code, {"file.sql": "SELECT 1;"}
    )

    monitor = await Monitor.get(Monitor.name == monitor_name)
    assert monitor is not None
    assert response_data == {
        "status": "monitor_registered",
        "monitor_id": monitor.id,
    }

    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None
    assert code_module.code == monitor_code
    assert code_module.additional_files == {"file.sql": "SELECT 1;"}


async def test_monitor_register_missing_parameter():
    """The 'monitor register' route should return an error any required parameter is missing"""
    url = BASE_URL + "/register/test_monitor_register_missing_parameter"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={}) as response:
            assert await response.json() == {
                "status": "error",
                "message": "'monitor_code' parameter is required",
            }


async def test_monitor_register_dataclass_validation_error():
    """The 'monitor register' route should return an error if the provided module code has a
    'pydantic.ValidationError'"""
    request_payload = {
        "monitor_code": "\n".join([
            "from pydantic.dataclasses import dataclass",
            "\n",
            "@dataclass",
            "class Data:",
            "    value: str",
            "\n",
            "data = Data(value=123)",
        ]),
    }

    url = BASE_URL + "/register/test_monitor_register_dataclass_validation_error"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "message": "Type validation error",
                "error": [
                    {
                        "loc": ["value"],
                        "type": "string_type",
                        "msg": "Input should be a valid string",
                    },
                ],
            }


async def test_monitor_register_check_fail(caplog):
    """The 'monitor register' route should return an error if the provided module code is invalid"""
    monitor_code = "import time"

    request_payload = {
        "monitor_code": monitor_code,
    }

    url = BASE_URL + "/register/test_monitor_register_check_fail"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "message": "Module didn't pass check",
                "error": "\n".join([
                    "Monitor 'test_monitor_register_check_fail' has the following errors:",
                    "  'monitor_options' is required",
                    "  'issue_options' is required",
                    "  'IssueDataType' is required",
                    "  'search' function is required",
                    "  'update' function is required",
                ]),
            }


@pytest.mark.parametrize("monitor_code, expected_error", [
    ("something", "name 'something' is not defined"),
    ("import time;\n\ntime.abc()", "module 'time' has no attribute 'abc'"),
    (
        "print('a",
        "unterminated string literal (detected at line 1) "
        "(test_monitor_register_invalid_monitor_code.py, line 1)"
    ),
])
async def test_monitor_register_invalid_monitor_code(monitor_code, expected_error):
    """The 'monitor register' route should return an error if the provided module code has any
    errors"""
    request_payload = {
        "monitor_code": monitor_code,
    }

    url = BASE_URL + "/register/test_monitor_register_invalid_monitor_code"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "error": expected_error,
            }

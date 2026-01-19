from unittest.mock import AsyncMock

import aiohttp
import pytest
import pytest_asyncio

import commands as commands
import components.controller.controller as controller
import components.http_server as http_server
import databases as databases
from models import Alert, AlertStatus, CodeModule, Monitor

pytestmark = pytest.mark.asyncio(loop_scope="session")

BASE_URL = "http://localhost:8000/monitor"


@pytest_asyncio.fixture(loop_scope="session", scope="module", autouse=True)
async def setup_http_server():
    """Start the HTTP server"""
    controller.running = True
    await http_server.init(controller_enabled=True)
    yield
    await http_server.wait_stop()


async def test_list_monitors(clear_database, sample_monitor: Monitor):
    """The 'monitor list' route should return a list of all monitors"""
    url = BASE_URL + "/list"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == [
        {
            "id": sample_monitor.id,
            "name": sample_monitor.name,
            "enabled": sample_monitor.enabled,
            "active_alerts": 0,
        },
    ]


@pytest.mark.parametrize("active_alerts", range(1, 5))
async def test_list_monitors_with_alerts(clear_database, sample_monitor: Monitor, active_alerts):
    """The 'monitor list' route should return a list of all monitors and the count of active alerts
    for them"""
    await Alert.create_batch(
        Alert(
            monitor_id=sample_monitor.id,
            priority=i,
            acknowledge_priority=5 - i,
        )
        for i in range(active_alerts)
    )
    await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
        priority=1,
        acknowledge_priority=1,
    )

    url = BASE_URL + "/list"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == [
        {
            "id": sample_monitor.id,
            "name": sample_monitor.name,
            "enabled": sample_monitor.enabled,
            "active_alerts": active_alerts,
        },
    ]


async def test_list_monitors_not_enabled(clear_database, sample_monitor: Monitor):
    """The 'monitor list' route should return a list of all monitors and the count of active alerts
    for them"""
    await Alert.create(
        monitor_id=sample_monitor.id,
        priority=1,
        acknowledge_priority=1,
    )
    sample_monitor.enabled = False
    await sample_monitor.save()

    url = BASE_URL + "/list"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == [
        {
            "id": sample_monitor.id,
            "name": sample_monitor.name,
            "enabled": sample_monitor.enabled,
            "active_alerts": 0,
        },
    ]


@pytest.mark.parametrize("alerts_number", [1, 2])
async def test_list_monitor_active_alerts(clear_database, alerts_number, sample_monitor: Monitor):
    """The 'monitor active alerts' route should return a list of all active alerts for a monitor"""
    alerts = await Alert.create_batch(
        Alert(
            monitor_id=sample_monitor.id,
            priority=i,
            acknowledge_priority=5 - 1,
        )
        for i in range(alerts_number)
    )

    url = BASE_URL + f"/{sample_monitor.id}/alerts"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert isinstance(response_data, list)
    assert len(response_data) == alerts_number
    for alert, response_alert in zip(alerts, response_data):
        assert alert.id == response_alert["id"]
        assert alert.status == response_alert["status"]
        assert alert.acknowledged == response_alert["acknowledged"]
        assert alert.locked == response_alert["locked"]
        assert alert.priority == response_alert["priority"]
        assert alert.acknowledge_priority == response_alert["acknowledge_priority"]
        assert alert.can_acknowledge == response_alert["can_acknowledge"]
        assert alert.can_lock == response_alert["can_lock"]
        assert alert.can_solve == response_alert["can_solve"]
        assert alert.created_at.strftime("%Y-%m-%d %H:%M:%S") == response_alert["created_at"]


async def test_get_monitor(clear_database, sample_monitor: Monitor):
    """The 'monitor get' route should return the monitor attributes and code information"""
    code_module = await CodeModule.get(CodeModule.monitor_id == sample_monitor.id)
    assert code_module is not None

    code_module.code = 'print("Sample code")'
    code_module.additional_files = {"file.sql": "SELECT 1;"}
    await code_module.save()

    url = BASE_URL + f"/{sample_monitor.name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == {
        "id": sample_monitor.id,
        "name": sample_monitor.name,
        "enabled": sample_monitor.enabled,
        "code": 'print("Sample code")',
        "additional_files": {"file.sql": "SELECT 1;"},
    }


async def test_get_monitor_invalid_monitor(clear_database):
    """The 'monitor get' route should return an error if the monitor is not found"""
    url = BASE_URL + "/not_found"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == {
        "status": "monitor_not_found",
    }


async def test_get_monitor_invalid_code_module(clear_database, sample_monitor: Monitor):
    """The 'monitor get' route should return an error if the monitor has no code module"""
    await databases.execute_application(
        'delete from "CodeModules" where monitor_id = $1', sample_monitor.id
    )

    url = BASE_URL + f"/{sample_monitor.name}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_data = await response.json()

    assert response_data == {
        "status": "monitor_code_not_found",
    }


async def test_monitor_disable(mocker, clear_database, sample_monitor: Monitor):
    """The 'monitor disable' route should disable a monitor"""
    monitor_disable_spy: AsyncMock = mocker.spy(commands, "disable_monitor")

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
    monitor_disable_spy: AsyncMock = mocker.spy(commands, "disable_monitor")

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
    monitor_disable_spy: AsyncMock = mocker.spy(commands, "disable_monitor")
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
    monitor_enable_spy: AsyncMock = mocker.spy(commands, "enable_monitor")

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
    monitor_enable_spy: AsyncMock = mocker.spy(commands, "enable_monitor")

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
    monitor_enable_spy: AsyncMock = mocker.spy(commands, "enable_monitor")
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


async def test_monitor_validate(mocker):
    """The 'monitor validate' route should validate the provided module code"""
    monitor_code_validate_spy: AsyncMock = mocker.spy(commands, "monitor_code_validate")

    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    request_payload = {"monitor_code": monitor_code}

    url = BASE_URL + "/validate"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            response_data = await response.json()

    assert response_data == {"status": "monitor_validated"}
    monitor_code_validate_spy.assert_awaited_once_with(monitor_code)


async def test_monitor_validate_missing_monitor_code():
    """The 'monitor validate' route should return an error any required parameter is missing"""
    url = BASE_URL + "/validate"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json={}) as response:
            assert await response.json() == {
                "status": "error",
                "message": "'monitor_code' parameter is required",
            }


async def test_monitor_validate_dataclass_validation_error():
    """The 'monitor validate' route should return an error if the provided module code has a
    'pydantic.ValidationError'"""
    request_payload = {
        "monitor_code": "\n".join(
            [
                "from pydantic.dataclasses import dataclass",
                "\n",
                "@dataclass",
                "class Data:",
                "    value: str",
                "\n",
                "data = Data(value=123)",
            ]
        ),
    }

    url = BASE_URL + "/validate"
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


async def test_monitor_validate_check_fail():
    """The 'monitor validate' route should return an error if the provided module code is invalid"""
    monitor_code = "import time"

    request_payload = {"monitor_code": monitor_code}

    url = BASE_URL + "/validate"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "message": "Module didn't pass check",
                "error": "\n".join(
                    [
                        "Monitor has the following errors:",
                        "  'monitor_options' is required",
                        "  'issue_options' is required",
                        "  'IssueDataType' is required",
                        "  'search' function is required",
                        "  'update' function is required",
                    ]
                ),
            }


async def test_monitor_validate_syntax_error(mocker):
    """The 'monitor validate' route should return an error if the provided module code has any
    errors"""
    request_payload = {
        "monitor_code": "print('a",
    }

    url = BASE_URL + "/validate"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "error": "'print('a' unterminated string literal (detected at line 1)",
            }


@pytest.mark.parametrize(
    "monitor_code, expected_error",
    [
        ("something", "name 'something' is not defined"),
        ("import time;\n\ntime.abc()", "module 'time' has no attribute 'abc'"),
    ],
)
async def test_monitor_validate_invalid_monitor_code(mocker, monitor_code, expected_error):
    """The 'monitor validate' route should return an error if the provided module code has any
    errors"""
    request_payload = {
        "monitor_code": monitor_code,
    }

    url = BASE_URL + "/validate"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=request_payload) as response:
            assert await response.json() == {
                "status": "error",
                "error": expected_error,
            }


@pytest.mark.parametrize(
    "monitor_name, expected_formatted_name",
    [
        ("test_monitor_format_name", "test_monitor_format_name"),
        ("a.b.c", "a_b_c"),
        ("My.Monitor-Name@123", "my_monitorname123"),
    ],
)
async def test_format_name(monitor_name, expected_formatted_name):
    """The 'format name' route should return the formatted name of the monitor"""
    url = BASE_URL + f"/format_name/{monitor_name}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            assert await response.json() == {
                "name": monitor_name,
                "formatted_name": expected_formatted_name,
            }


@pytest.mark.parametrize(
    "monitor_name",
    [
        "test_monitor_register",
        "test_monitor_register_different_name",
        "test.monitor.register.name.with.dots",
    ],
)
async def test_monitor_register(mocker, clear_database, monitor_name):
    """The 'monitor register' route should register a new monitor with the provided module code if
    it doesn't exists. The monitor name should replace any dots with underscores"""
    monitor_register_spy: AsyncMock = mocker.spy(commands, "monitor_register")

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
    monitor_register_spy: AsyncMock = mocker.spy(commands, "monitor_register")

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
        "monitor_code": "\n".join(
            [
                "from pydantic.dataclasses import dataclass",
                "\n",
                "@dataclass",
                "class Data:",
                "    value: str",
                "\n",
                "data = Data(value=123)",
            ]
        ),
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


async def test_monitor_register_check_fail():
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
                "error": "\n".join(
                    [
                        "Monitor 'test_monitor_register_check_fail' has the following errors:",
                        "  'monitor_options' is required",
                        "  'issue_options' is required",
                        "  'IssueDataType' is required",
                        "  'search' function is required",
                        "  'update' function is required",
                    ]
                ),
            }


@pytest.mark.parametrize(
    "monitor_code, expected_error",
    [
        ("something", "name 'something' is not defined"),
        ("import time;\n\ntime.abc()", "module 'time' has no attribute 'abc'"),
        (
            "print('a",
            "unterminated string literal (detected at line 1) "
            "(test_monitor_register_invalid_monitor_code.py, line 1)",
        ),
    ],
)
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

import json
from unittest.mock import AsyncMock

import pytest

import commands.requests as requests
import components.monitors_loader as monitors_loader
from models import CodeModule, Monitor
from tests.message_queue.utils import get_queue_items

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_monitor_register(mocker):
    """'monitor_register' function should register a monitor with the provided name and module
    code"""
    register_monitor_spy: AsyncMock = mocker.spy(monitors_loader, "register_monitor")

    monitor_name = "test_monitor_register"
    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await requests.monitor_register(monitor_name, monitor_code, {})
    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None

    register_monitor_spy.assert_awaited_once_with(monitor_name, monitor_code, additional_files={})
    assert monitor.name == monitor_name
    assert code_module.additional_files == {}


async def test_monitor_register_additional_files(mocker):
    """'monitor_register' function should register a monitor with the provided name and module
    code"""
    register_monitor_spy: AsyncMock = mocker.spy(monitors_loader, "register_monitor")

    monitor_name = "test_monitor_register"
    with open("tests/sample_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await requests.monitor_register(monitor_name, monitor_code, {"file.sql": "SELECT 1;"})
    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None

    register_monitor_spy.assert_awaited_once_with(
        monitor_name, monitor_code, additional_files={"file.sql": "SELECT 1;"}
    )
    assert monitor.name == monitor_name
    assert code_module.additional_files == {"file.sql": "SELECT 1;"}


async def test_disable_monitor(mocker, sample_monitor: Monitor):
    """'disable_monitor' should disable the monitor with the provided name"""
    assert sample_monitor.enabled is True
    result = await requests.disable_monitor(sample_monitor.name)
    assert result == f"{sample_monitor} disabled"
    await sample_monitor.refresh()
    assert sample_monitor.enabled is False


async def test_disable_monitor_not_found():
    """'disable_monitor' should raise a 'ValueError' exception if the monitor is not found"""
    with pytest.raises(ValueError, match="Monitor 'not_found' not found"):
        await requests.disable_monitor("not_found")


async def test_enable_monitor(mocker, sample_monitor: Monitor):
    """'disable_monitor' should enable the monitor with the provided name"""
    await sample_monitor.set_enabled(False)
    await sample_monitor.refresh()
    assert sample_monitor.enabled is False
    result = await requests.enable_monitor(sample_monitor.name)
    assert result == f"{sample_monitor} enabled"
    await sample_monitor.refresh()
    assert sample_monitor.enabled is True


async def test_enable_monitor_not_found(mocker):
    """'enable_monitor' should raise a 'ValueError' exception if the monitor is not found"""
    with pytest.raises(ValueError, match="Monitor 'not_found' not found"):
        await requests.enable_monitor("not_found")


@pytest.mark.parametrize("target_id", [1, 12, 345])
async def test_alert_acknowledge(clear_queue, target_id):
    """'alert_acknowledge' should queue an 'alert_acknowledge' action request"""
    await requests.alert_acknowledge(target_id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_acknowledge",
                    "params": {"target_id": target_id},
                },
            }
        )
    ]


@pytest.mark.parametrize("target_id", [1, 12, 345])
async def test_alert_lock(clear_queue, target_id):
    """'alert_lock' should queue an 'alert_lock' action request"""
    await requests.alert_lock(target_id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_lock",
                    "params": {"target_id": target_id},
                },
            }
        )
    ]


@pytest.mark.parametrize("target_id", [1, 12, 345])
async def test_alert_solve(clear_queue, target_id):
    """'alert_solve' should queue an 'alert_solve' action request"""
    await requests.alert_solve(target_id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_solve",
                    "params": {"target_id": target_id},
                },
            }
        )
    ]


@pytest.mark.parametrize("target_id", [1, 12, 345])
async def test_issue_drop(clear_queue, target_id):
    """'issue_drop' should queue an 'issue_drop' action request"""
    await requests.issue_drop(target_id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "issue_drop",
                    "params": {"target_id": target_id},
                },
            }
        )
    ]

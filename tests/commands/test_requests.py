import json
import re
from unittest.mock import AsyncMock, MagicMock

import pytest

import commands.requests as requests
import components.monitors_loader as monitors_loader
from commands.exceptions import AlertNotFoundError, IssueNotFoundError, MonitorNotFoundError
from models import Alert, CodeModule, Issue, Monitor
from tests.message_queue.utils import get_queue_items

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_monitor_code_validate(mocker):
    """'monitor_code_validate' function should validate a monitor code"""
    check_monitor_spy: MagicMock = mocker.spy(monitors_loader, "check_monitor")

    with open("tests/example_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    await requests.monitor_code_validate(monitor_code)

    check_monitor_spy.assert_called_once()

    call_args = check_monitor_spy.call_args
    assert len(call_args.args) == 2
    monitor_name_regex = r"monitor_\d{10}_[a-z]{8}"
    assert re.match(monitor_name_regex, call_args.args[0]) is not None
    assert call_args.args[1] == monitor_code


async def test_monitor_register(mocker):
    """'monitor_register' function should register a monitor with the provided name and module
    code"""
    register_monitor_spy: AsyncMock = mocker.spy(monitors_loader, "register_monitor")

    monitor_name = "test_monitor_register"
    with open("tests/example_monitors/others/monitor_1/monitor_1.py", "r") as file:
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
    with open("tests/example_monitors/others/monitor_1/monitor_1.py", "r") as file:
        monitor_code = file.read()

    monitor = await requests.monitor_register(monitor_name, monitor_code, {"file.sql": "SELECT 1;"})
    code_module = await CodeModule.get(CodeModule.monitor_id == monitor.id)
    assert code_module is not None

    register_monitor_spy.assert_awaited_once_with(
        monitor_name, monitor_code, additional_files={"file.sql": "SELECT 1;"}
    )
    assert monitor.name == monitor_name
    assert code_module.additional_files == {"file.sql": "SELECT 1;"}


async def test_monitor_disable(clear_queue, sample_monitor: Monitor):
    """'monitor_disable' should queue a 'monitor_disable' action request"""
    result = await requests.monitor_disable(sample_monitor.name)
    assert result == sample_monitor.id

    queue_items = get_queue_items()
    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "monitor_disable",
                    "params": {"target_id": sample_monitor.id},
                },
            }
        )
    ]


async def test_monitor_disable_not_found():
    """'monitor_disable' should raise a 'MonitorNotFoundError' exception if the monitor is not
    found"""
    with pytest.raises(MonitorNotFoundError, match="Monitor 'not_found' not found"):
        await requests.monitor_disable("not_found")


async def test_monitor_enable(clear_queue, sample_monitor: Monitor):
    """'monitor_enable' should queue a 'monitor_enable' action request"""
    result = await requests.monitor_enable(sample_monitor.name)
    assert result == sample_monitor.id

    queue_items = get_queue_items()
    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "monitor_enable",
                    "params": {"target_id": sample_monitor.id},
                },
            }
        )
    ]


async def test_monitor_enable_not_found():
    """'monitor_enable' should raise a 'MonitorNotFoundError' exception if the monitor is not
    found"""
    with pytest.raises(MonitorNotFoundError, match="Monitor 'not_found' not found"):
        await requests.monitor_enable("not_found")


async def test_alert_acknowledge(clear_queue, sample_monitor: Monitor):
    """'alert_acknowledge' should queue an 'alert_acknowledge' action request"""
    alert = await Alert.create(monitor_id=sample_monitor.id)
    await requests.alert_acknowledge(alert.id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_acknowledge",
                    "params": {"target_id": alert.id},
                },
            }
        )
    ]


async def test_alert_acknowledge_not_found():
    """'alert_acknowledge' should raise an 'AlertNotFoundError' exception if alert is not found"""
    with pytest.raises(AlertNotFoundError, match="Alert '999999999' not found"):
        await requests.alert_acknowledge(999999999)


async def test_alert_lock(clear_queue, sample_monitor: Monitor):
    """'alert_lock' should queue an 'alert_lock' action request"""
    alert = await Alert.create(monitor_id=sample_monitor.id)
    await requests.alert_lock(alert.id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_lock",
                    "params": {"target_id": alert.id},
                },
            }
        )
    ]


async def test_alert_lock_not_found():
    """'alert_lock' should raise an 'AlertNotFoundError' exception if alert is not found"""
    with pytest.raises(AlertNotFoundError, match="Alert '999999999' not found"):
        await requests.alert_lock(999999999)


async def test_alert_solve(clear_queue, sample_monitor: Monitor):
    """'alert_solve' should queue an 'alert_solve' action request"""
    alert = await Alert.create(monitor_id=sample_monitor.id)
    await requests.alert_solve(alert.id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "alert_solve",
                    "params": {"target_id": alert.id},
                },
            }
        )
    ]


async def test_alert_solve_not_found():
    """'alert_solve' should raise an 'AlertNotFoundError' exception if alert is not found"""
    with pytest.raises(AlertNotFoundError, match="Alert '999999999' not found"):
        await requests.alert_solve(999999999)


async def test_issue_drop(clear_queue, sample_monitor: Monitor):
    """'issue_drop' should queue an 'issue_drop' action request"""
    issue = await Issue.create(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})
    await requests.issue_drop(issue.id)

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "issue_drop",
                    "params": {"target_id": issue.id},
                },
            }
        )
    ]


async def test_issue_drop_not_found():
    """'issue_drop' should raise an 'IssueNotFoundError' exception if issue is not found"""
    with pytest.raises(IssueNotFoundError, match="Issue '999999999' not found"):
        await requests.issue_drop(999999999)

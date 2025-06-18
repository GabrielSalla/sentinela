import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

import components.executor.request_handler as request_handler
import plugins as plugins
import registry as registry
from base_exception import BaseSentinelaException
from configs import configs
from data_models.request_payload import RequestPayload
from models import Alert, AlertStatus, Issue, IssueStatus, Monitor
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_alert_acknowledge(mocker, sample_monitor: Monitor):
    """'alert_acknowledge' should acknowledge the provided alert"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    acknowledge_spy: AsyncMock = mocker.spy(Alert, "acknowledge")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    assert not alert.acknowledged

    await request_handler.alert_acknowledge(
        RequestPayload(action="alert_acknowledge", params={"target_id": alert.id})
    )

    await alert.refresh()

    assert alert.acknowledged
    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    acknowledge_spy.assert_awaited_once()


async def test_alert_acknowledge_alert_not_found(caplog, mocker):
    """'alert_acknowledge' should just return when an alert with the provided id doesn't exists"""
    acknowledge_spy: AsyncMock = mocker.spy(Alert, "acknowledge")

    await request_handler.alert_acknowledge(
        RequestPayload(action="alert_acknowledge", params={"target_id": 999999999})
    )

    acknowledge_spy.assert_not_called()
    assert_message_in_log(caplog, "Alert '999999999' not found")


async def test_alert_lock(mocker, sample_monitor: Monitor):
    """'alert_lock' should lock the provided alert"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    lock_spy: AsyncMock = mocker.spy(Alert, "lock")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    assert not alert.locked

    await request_handler.alert_lock(
        RequestPayload(action="alert_lock", params={"target_id": alert.id})
    )

    await alert.refresh()

    assert alert.locked
    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    lock_spy.assert_awaited_once()


async def test_alert_lock_alert_not_found(caplog, mocker):
    """'alert_lock' should just return when an alert with the provided id doesn't exists"""
    lock_spy: AsyncMock = mocker.spy(Alert, "lock")

    await request_handler.alert_lock(
        RequestPayload(action="alert_lock", params={"target_id": 999999999})
    )

    lock_spy.assert_not_called()
    assert_message_in_log(caplog, "Alert '999999999' not found")


async def test_alert_solve(mocker, monkeypatch, sample_monitor: Monitor):
    """'alert_solve' should solve all the alert's issues and update it's status"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    monkeypatch.setattr(sample_monitor.code.issue_options, "solvable", False)
    solve_spy: AsyncMock = mocker.spy(Alert, "solve")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    assert alert.status == AlertStatus.active

    await request_handler.alert_solve(
        RequestPayload(action="alert_solve", params={"target_id": alert.id})
    )

    await alert.refresh()

    assert alert.status == AlertStatus.solved
    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    solve_spy.assert_awaited_once()


async def test_alert_solve_alert_not_found(caplog, mocker):
    """'alert_solve' should just return when an alert with the provided id doesn't exists"""
    solve_spy: AsyncMock = mocker.spy(Alert, "solve")

    await request_handler.alert_solve(
        RequestPayload(action="alert_lock", params={"target_id": 999999999})
    )

    solve_spy.assert_not_called()
    assert_message_in_log(caplog, "Alert '999999999' not found")


async def test_issue_drop(mocker, sample_monitor: Monitor):
    """'issue_drop' should drop the provided issue"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    drop_spy: AsyncMock = mocker.spy(Issue, "drop")

    issue = await Issue.create(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})
    assert issue.status == IssueStatus.active

    await request_handler.issue_drop(
        RequestPayload(action="issue_drop", params={"target_id": issue.id})
    )

    await issue.refresh()

    assert issue.status == IssueStatus.dropped
    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    drop_spy.assert_awaited_once()


async def test_issue_drop_issue_not_found(caplog, mocker):
    """'issue_drop' should just return when an issue with the provided id doesn't exists"""
    drop_spy: AsyncMock = mocker.spy(Issue, "drop")

    await request_handler.issue_drop(
        RequestPayload(action="issue_drop", params={"target_id": 999999999})
    )

    drop_spy.assert_not_called()
    assert_message_in_log(caplog, "Issue '999999999' not found")


async def test_get_action():
    """'get_action' should return the action function by its name"""
    assert request_handler.get_action("alert_acknowledge") == request_handler.alert_acknowledge
    assert request_handler.get_action("alert_lock") == request_handler.alert_lock
    assert request_handler.get_action("alert_solve") == request_handler.alert_solve
    assert request_handler.get_action("issue_drop") == request_handler.issue_drop


async def test_get_action_plugin(monkeypatch):
    """'get_action' should return the action function by its name when it's from a plugin"""

    class Plugin:
        class actions:
            @staticmethod
            async def test_action(message_payload): ...

    monkeypatch.setattr(plugins, "loaded_plugins", {"plugin1": Plugin}, raising=False)

    expected_action = Plugin.actions.test_action
    assert request_handler.get_action("plugin.plugin1.actions.test_action") == expected_action


async def test_get_action_unknown_plugin(caplog, monkeypatch):
    """'get_action' should return 'None' when the attribute path could not be resolved"""
    monkeypatch.setattr(
        request_handler,
        "get_plugin_attribute",
        MagicMock(side_effect=ValueError("Some error from the function")),
    )

    action = request_handler.get_action("plugin.plugin2.test_action")

    assert action is None
    assert_message_in_log(caplog, "Some error from the function")


@pytest.mark.parametrize(
    "action_name",
    ["alert_acknowledge", "alert_lock", "alert_solve", "issue_drop"],
)
async def test_run_action(monkeypatch, action_name):
    """'run' should executed the requested action"""

    async def do_nothing(message_payload): ...

    action_mock = AsyncMock(side_effect=do_nothing)
    monkeypatch.setitem(request_handler.actions, action_name, action_mock)

    await request_handler.run(
        {"payload": {"action": action_name, "params": {"target_id": 999999999}}}
    )

    action_mock.assert_awaited_once_with(
        RequestPayload(action=action_name, params={"target_id": 999999999})
    )


async def test_run_invalid_payload(caplog):
    """'run' should log an error if the payload is invalid and just return"""
    await request_handler.run({})
    assert_message_in_log(caplog, "Message '{}' missing 'payload' field")


async def test_run_payload_wrong_structure(caplog):
    """'run' should log an error if the payload has the wrong structure and just return"""
    await request_handler.run({"payload": {}})
    assert_message_in_log(caplog, "Invalid payload: 2 validation errors for RequestPayload")


async def test_run_unknown_action(caplog):
    """'run' should just return if there isn't an action mapped for the action requested"""
    await request_handler.run({"payload": {"action": "test", "params": {"target_id": 1}}})
    assert_message_in_log(
        caplog, 'Got request with unknown action \'{"action": "test", "params": {"target_id": 1}}\''
    )


@pytest.mark.flaky(reruns=2)
async def test_run_timeout(caplog, monkeypatch):
    """'run' should timeout the request if it takes too long to execute"""
    monkeypatch.setattr(configs, "executor_request_timeout", 0.2)

    async def sleep(message_payload):
        await asyncio.sleep(1)

    action_mock = AsyncMock(side_effect=sleep)
    monkeypatch.setitem(request_handler.actions, "test", action_mock)

    start_time = time.perf_counter()
    await request_handler.run({"payload": {"action": "test", "params": {"target_id": 1}}})
    end_time = time.perf_counter()

    total_time = end_time - start_time
    assert total_time > 0.2 - 0.001
    assert total_time < 0.2 + 0.005

    action_mock.assert_awaited_once()

    assert_message_in_log(caplog, "Timed out executing request")


async def test_run_sentinela_exception(monkeypatch):
    """'run' should re-raise Sentinela exceptions"""

    class SomeException(BaseSentinelaException):
        pass

    async def error(message_payload):
        raise SomeException("Some Sentinela exception")

    action_mock = AsyncMock(side_effect=error)
    monkeypatch.setitem(request_handler.actions, "test", action_mock)

    with pytest.raises(SomeException):
        await request_handler.run({"payload": {"action": "test", "params": {"target_id": 1}}})


async def test_run_error(caplog, monkeypatch):
    """'run' should handle errors when executing requests"""

    async def error(message_payload):
        raise ValueError("Nothing good happens")

    action_mock = AsyncMock(side_effect=error)
    monkeypatch.setitem(request_handler.actions, "test", action_mock)

    await request_handler.run({"payload": {"action": "test", "params": {"target_id": 1}}})

    assert_message_in_log(
        caplog, 'Error executing request \'{"action": "test", "params": {"target_id": 1}}\''
    )
    assert_message_in_log(caplog, "ValueError: Nothing good happens")

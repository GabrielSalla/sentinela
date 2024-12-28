import logging
from unittest.mock import MagicMock

import pytest

import utils.time as time_utils
from models import Alert, Issue, IssueStatus, Monitor
from registry import registry
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("issue_status", IssueStatus)
async def test_is_unique_active(sample_monitor: Monitor, issue_status):
    """'Issue.is_unique' should return if the provided 'model_id' is unique for the monitor, for
    any possible issue status"""
    is_unique = await Issue.is_unique(sample_monitor.id, "12345")
    assert is_unique

    await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        status=issue_status,
    )

    is_unique = await Issue.is_unique(sample_monitor.id, "12345")
    assert not is_unique


async def test_options(sample_monitor: Monitor):
    """'Issue.options' should return the monitor's 'issue_options' from it's code module"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert issue.options == monitor_code.issue_options


async def test_is_solved(monkeypatch, sample_monitor: Monitor):
    """'Issue.is_solved' should return if the current issue's data is considered as solved by the
    monitor's module 'is_solved' function"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    is_solved_true_mock = MagicMock(return_value=True)
    is_solved_false_mock = MagicMock(return_value=False)
    monitor_code = registry._monitors[sample_monitor.id]["module"]

    monkeypatch.setattr(monitor_code, "is_solved", is_solved_true_mock)
    assert issue.is_solved

    monkeypatch.setattr(monitor_code, "is_solved", is_solved_false_mock)
    assert not issue.is_solved


async def test_is_solved_not_solvable(monkeypatch, sample_monitor: Monitor):
    """'Issue.is_solved' should return 'False' if the monitor's 'issue_options.solvable' is set
    to 'False'"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code.issue_options, "solvable", False)
    is_solved_true_mock = MagicMock(return_value=True)
    monkeypatch.setattr(monitor_code, "is_solved", is_solved_true_mock)

    assert not issue.is_solved


async def test_link_to_alert_callback(caplog, mocker, sample_monitor: Monitor):
    """'Issue._link_to_alert_callback' should try to queue an 'issue_linked' event"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        alert_id=alert.id,
    )

    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue._link_to_alert_callback()

    issue_create_event_spy.assert_called_once_with("issue_linked")
    assert_message_in_log(caplog, f"Linked to alert '{alert.id}'")


async def test_link_to_alert_active(mocker, sample_monitor: Monitor):
    """'Issue.link_to_alert' should link the issue to the alert if the issue's status is 'active'
    and the callback should be executed"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )
    alert = await Alert.create(monitor_id=sample_monitor.id)

    callback_spy: MagicMock = mocker.spy(issue, "_link_to_alert_callback")

    await issue.link_to_alert(alert)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].alert_id == alert.id
    callback_spy.assert_called_once_with()


@pytest.mark.parametrize("issue_status", [IssueStatus.dropped, IssueStatus.solved])
async def test_link_to_alert_not_active(caplog, mocker, sample_monitor: Monitor, issue_status):
    """'Issue.link_to_alert' should not link the issue to the alert if the issue's status is not
    'active' and the callback should not be executed"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        status=issue_status,
    )
    alert = await Alert.create(monitor_id=sample_monitor.id)

    callback_spy: MagicMock = mocker.spy(issue, "_link_to_alert_callback")

    await issue.link_to_alert(alert)

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].alert_id is None

    assert_message_in_log(caplog, f"Can't link to alert, status is '{issue_status.value}'")
    callback_spy.assert_not_called()


async def test_check_solved_active_solved(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'Issue.check_solved' should check if the issue is solved and, if positive, solve the issue"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code, "is_solved", lambda issue_data: True)
    issue_solve_spy: MagicMock = mocker.spy(issue, "solve")

    await issue.check_solved()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == IssueStatus.solved
    issue_solve_spy.assert_called_once()


async def test_check_solved_active_not_solved(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'Issue.check_solved' should check if the issue is solved and, if negative, not solve the
    issue"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code, "is_solved", lambda issue_data: False)
    issue_solve_spy: MagicMock = mocker.spy(issue, "solve")

    await issue.check_solved()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == IssueStatus.active
    issue_solve_spy.assert_not_called()


@pytest.mark.parametrize("issue_status", [IssueStatus.dropped, IssueStatus.solved])
async def test_check_solved_not_active(caplog, mocker, sample_monitor: Monitor, issue_status):
    """'Issue.check_solved' should not check if the issue is solved if the issue's status is not
    'active'"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        status=issue_status,
    )

    issue_solve_spy: MagicMock = mocker.spy(issue, "solve")

    await issue.check_solved()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == issue_status

    issue_solve_spy.assert_not_called()
    assert_message_in_log(caplog, f"Can't check solved, status is '{issue_status.value}'")


async def test_drop_active(caplog, mocker, sample_monitor: Monitor):
    """'Issue.drop' should set the issue as 'dropped' if if the issue is active"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue.drop()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == IssueStatus.dropped
    dropped_at_delay = time_utils.time_since(issues[0].dropped_at)
    assert 0 < dropped_at_delay < 0.05

    issue_create_event_spy.assert_called_once_with("issue_dropped")
    assert_message_in_log(caplog, "Dropped")


@pytest.mark.parametrize("issue_status", [IssueStatus.dropped, IssueStatus.solved])
async def test_drop_not_active(caplog, mocker, sample_monitor: Monitor, issue_status):
    """'Issue.drop' should not set the issue as 'dropped' if the issue's status is not 'active'"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        status=issue_status,
    )

    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue.drop()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == issue_status
    assert issues[0].dropped_at is None

    issue_create_event_spy.assert_not_called()
    assert_message_in_log(caplog, f"Can't drop, status is '{issue_status.value}'")
    assert_message_not_in_log(caplog, "Dropped")


async def test_solve_callback(caplog, mocker, sample_monitor: Monitor):
    """'Issue._solve_callback' should try to queue an 'issue_solved' event"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue._solve_callback()

    issue_create_event_spy.assert_called_once_with("issue_solved")
    assert_message_in_log(caplog, "Solved")


async def test_solve_active(caplog, mocker, sample_monitor: Monitor):
    """'Issue.solve' should set the issue as solved if if the issue is active and the callback
    should be executed"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    callback_spy: MagicMock = mocker.spy(issue, "_solve_callback")

    await issue.solve()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == IssueStatus.solved
    solved_at_delay = time_utils.time_since(issues[0].solved_at)
    assert 0 < solved_at_delay < 0.05

    callback_spy.assert_called_once_with()


@pytest.mark.parametrize("issue_status", [IssueStatus.dropped, IssueStatus.solved])
async def test_solve_not_active(caplog, mocker, sample_monitor: Monitor, issue_status):
    """'Issue.solve' should not solve the issue if the issue's status is not 'active' and the
    callback should not be executed"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
        status=issue_status,
    )

    callback_spy: MagicMock = mocker.spy(issue, "_solve_callback")

    await issue.solve()

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].status == issue_status
    assert issues[0].solved_at is None

    callback_spy.assert_not_called()
    assert_message_in_log(caplog, f"Can't solve, status is '{issue_status.value}'")


async def test_update_data_callback_solved(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'Issue._update_data_callback' should try to queue an 'issue_updated_solved' event if the
    current issue data is considered as solved"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code, "is_solved", lambda issue_data: True)
    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue._update_data_callback()

    issue_create_event_spy.assert_called_once_with("issue_updated_solved")
    assert_message_in_log(caplog, "Data updated to '{\"id\": 1}'")


async def test_update_data_callback_not_solved(
    caplog, mocker, monkeypatch, sample_monitor: Monitor
):
    """'Issue._update_data_callback' should try to queue an 'issue_updated_not_solved' event if the
    current issue data is considered as not solved"""
    caplog.set_level(logging.DEBUG)

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 12},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code, "is_solved", lambda issue_data: False)
    issue_create_event_spy: MagicMock = mocker.spy(issue, "_create_event")

    await issue._update_data_callback()

    issue_create_event_spy.assert_called_once_with("issue_updated_not_solved")
    assert_message_in_log(caplog, "Data updated to '{\"id\": 12}'")


async def test_update_data_active(mocker, monkeypatch, sample_monitor: Monitor):
    """'Issue.update_data' should update the issue data if if the issue is active and the callback
    should be executed"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="12345",
        data={"id": 1},
    )

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(monitor_code, "is_solved", lambda issue_data: True)
    callback_spy: MagicMock = mocker.spy(issue, "_update_data_callback")

    await issue.update_data({"id": 100})

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].data == {"id": 100}

    callback_spy.assert_called_once_with()


@pytest.mark.parametrize("issue_status", [IssueStatus.dropped, IssueStatus.solved])
async def test_update_data_not_active(caplog, mocker, sample_monitor: Monitor, issue_status):
    """'Issue.update_data' should not update the issue data if if the issue is not active and the
    callback should not be executed"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id, model_id="12345", data={"id": 1}, status=issue_status
    )

    callback_spy: MagicMock = mocker.spy(issue, "_update_data_callback")

    await issue.update_data({"id": 100})

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)

    assert len(issues) == 1
    assert issues[0].data == {"id": 1}

    callback_spy.assert_not_called()
    assert_message_in_log(caplog, f"Can't update, status is '{issue_status.value}'")

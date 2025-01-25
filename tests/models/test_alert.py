import logging
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import models.utils.priority as priority_utils
import utils.time as time_utils
from models import Alert, AlertPriority, AlertStatus, Issue, IssueStatus, Monitor
from options import AgeRule, AlertOptions, IssueOptions, PriorityLevels
from registry import registry
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_options(monkeypatch, sample_monitor: Monitor):
    """'Alert.options' should return the monitor's 'alert_options' from it's code module if it's
    defined"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(rule=AgeRule(priority_levels=PriorityLevels()))
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)

    alert = await Alert.create(monitor_id=sample_monitor.id)

    assert monitor_code.alert_options == alert_options
    assert alert.options == monitor_code.alert_options


async def test_options_not_defined(sample_monitor: Monitor):
    """'Alert.options' should return 'None' it the 'alert_options' attribute is not defined in the
    monitor code"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]

    with pytest.raises(AttributeError):
        monitor_code.alert_options

    alert = await Alert.create(monitor_id=sample_monitor.id)

    assert alert.options is None


async def test_issue_options(sample_monitor: Monitor):
    """'Alert.issue_options' should return the monitor's 'issue_options' from it's code module"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert alert.issue_options == monitor_code.issue_options


async def test_active_issues(sample_monitor: Monitor):
    """'Alert.active_issues' should return all the active issues that are linked to the alert"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    active_issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    solved_issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(10 + i),
                data={"id": 10 + i},
                status=IssueStatus.solved,
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    alert_active_issues = await alert.active_issues
    alert_active_issues_ids = {issue.id for issue in alert_active_issues}

    solved_issues_ids = {issue.id for issue in solved_issues}
    expected_active_issues_ids = {issue.id for issue in active_issues}

    assert alert_active_issues_ids == expected_active_issues_ids
    assert solved_issues_ids - alert_active_issues_ids == solved_issues_ids


@pytest.mark.parametrize(
    "acknowledged, acknowledge_priority, priority, expected_result",
    [
        (False, 1, 1, False),
        (False, 1, 5, False),
        (False, 5, 1, False),
        (False, None, 1, False),
        (True, 5, 1, False),
        (True, 5, 4, False),
        (True, 5, 5, True),
        (True, 2, 1, False),
        (True, 1, 1, True),
        (True, 1, 5, True),
        (True, 1, 2, True),
        (True, None, 1, False),
    ],
)
async def test_is_priority_acknowledged(
    sample_monitor: Monitor, acknowledged, acknowledge_priority, priority, expected_result
):
    """'Alert.is_priority_acknowledged' should return 'True' if the current alert priority is
    acknowledged, 'False' otherwise"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=acknowledged,
        acknowledge_priority=acknowledge_priority,
        priority=priority,
    )

    assert alert.is_priority_acknowledged == expected_result


async def test_calculate_priority(mocker, sample_monitor: Monitor):
    """'Alert.calculate_priority' should use the 'calculate_priority' function to calculate an
    alert priority"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    calculate_priority_spy: MagicMock = mocker.spy(priority_utils, "calculate_priority")

    rule = AgeRule(priority_levels=PriorityLevels())
    alert.calculate_priority(rule=rule, issues=issues)

    calculate_priority_spy.assert_called_once_with(rule=rule, issues=issues)


async def test_update_priority_without_alert_options(caplog, mocker, sample_monitor: Monitor):
    """'Alert.update_priority' should just return if there isn't an 'alert_option' configuration"""
    alert = await Alert.create(monitor_id=sample_monitor.id)

    calculate_priority_spy: MagicMock = mocker.spy(alert, "calculate_priority")

    assert alert.options is None

    await alert.update_priority()

    calculate_priority_spy.assert_not_called()
    assert_message_in_log(
        caplog, "Updating alert priority is not possible without an 'AlertOptions' setting"
    )


async def test_update_priority_none(monkeypatch, sample_monitor: Monitor):
    """'Alert.update_priority' should use 'low[4]' as a priority if the 'calculate_priority'
    returned 'None'"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id, priority=priority_utils.AlertPriority.critical
    )
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(rule=AgeRule(priority_levels=PriorityLevels()))
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)
    monkeypatch.setattr(priority_utils, "calculate_priority", lambda rule, issues: None)

    assert alert.priority == priority_utils.AlertPriority.critical
    assert priority_utils.calculate_priority(alert_options, []) is None

    await alert.update_priority()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.priority == priority_utils.AlertPriority.low


@pytest.mark.parametrize(
    "current_priority, new_priority",
    [
        (5, 4),
        (5, 3),
        (4, 2),
        (2, 1),
    ],
)
async def test_update_priority_higher_priority(
    caplog, mocker, monkeypatch, sample_monitor: Monitor, current_priority, new_priority
):
    """'Alert.update_priority' should update the alert's priority based on it's rule and active
    issues and try to queue an 'alert_priority_increased' event if the new priority is higher than
    the previous one"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=current_priority,
    )
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(rule=AgeRule(priority_levels=PriorityLevels()))
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)
    monkeypatch.setattr(priority_utils, "calculate_priority", lambda rule, issues: new_priority)
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update_priority()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.priority == new_priority

    alert_create_event_spy.assert_awaited_once_with(
        "alert_priority_increased", extra_payload={"previous_priority": current_priority}
    )
    assert_message_in_log(
        caplog, f"Alert priority increased from {current_priority} to {new_priority}"
    )
    assert_message_not_in_log(caplog, "Alert priority decreased")


@pytest.mark.parametrize(
    "current_priority, new_priority",
    [
        (4, 5),
        (3, 5),
        (2, 4),
        (1, 2),
    ],
)
async def test_update_priority_lower_priority(
    caplog, mocker, monkeypatch, sample_monitor: Monitor, current_priority, new_priority
):
    """'Alert.update_priority' should update the alert's priority based on it's rule and active
    issues and try to queue an 'alert_priority_decreased' event if the new priority is lower than
    the previous one"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=current_priority,
    )
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(rule=AgeRule(priority_levels=PriorityLevels()))
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)
    monkeypatch.setattr(priority_utils, "calculate_priority", lambda rule, issues: new_priority)
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update_priority()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.priority == new_priority

    assert_message_in_log(
        caplog, f"Alert priority decreased from {current_priority} to {new_priority}"
    )
    alert_create_event_spy.assert_awaited_once_with(
        "alert_priority_decreased", extra_payload={"previous_priority": current_priority}
    )
    assert_message_not_in_log(caplog, "Alert priority increased")


@pytest.mark.parametrize("priority", priority_utils.AlertPriority)
async def test_update_priority_same_priority(
    caplog, mocker, monkeypatch, sample_monitor: Monitor, priority
):
    """'Alert.update_priority' should update the alert's priority based on it's rule and active
    issues and do nothing if the new priority is the same as the current one"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=priority,
    )
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(rule=AgeRule(priority_levels=PriorityLevels()))
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)
    monkeypatch.setattr(priority_utils, "calculate_priority", lambda rule, issues: priority)
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update_priority()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.priority == priority

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Alert priority increased")
    assert_message_not_in_log(caplog, "Alert priority decreased")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_link_issues_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.link_issues' should not link the provided issues to the alert if the alert is
    solved"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
            )
            for i in range(5)
        ]
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.link_issues(issues)

    linked_issues = await Issue.get_all(Issue.alert_id == alert.id)
    assert len(linked_issues) == 0

    assert_message_in_log(caplog, f"Can't link issues, status is '{alert_status.value}'")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Issues linked")


async def test_link_issues_locked(caplog, mocker, sample_monitor: Monitor):
    """'Alert.link_issues' should not link the provided issues to the alert if the alert is
    locked"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        locked=True,
    )
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
            )
            for i in range(5)
        ]
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.link_issues(issues)

    linked_issues = await Issue.get_all(Issue.alert_id == alert.id)
    assert len(linked_issues) == 0

    assert_message_in_log(caplog, "Can't link issues, alert is locked")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Issues linked")


async def test_link_issues_issues_empty(caplog, mocker, sample_monitor: Monitor):
    """'Alert.link_issues' should just return if the list of issues is empty"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)

    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.link_issues([])

    linked_issues = await Issue.get_all(Issue.alert_id == alert.id)
    assert len(linked_issues) == 0

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Issues linked")


async def test_link_issues_linked(caplog, mocker, sample_monitor: Monitor):
    """'Alert.link_issues' should link the issues to the alert if all the necessary conditions
    are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
            )
            for i in range(5)
        ]
    )

    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.link_issues(issues)

    linked_issues = await Issue.get_all(Issue.alert_id == alert.id)
    issues_ids = {issue.id for issue in issues}
    linked_issues_ids = {issue.id for issue in linked_issues}
    assert linked_issues_ids == issues_ids

    alert_create_event_spy.assert_awaited_once_with(
        "alert_issues_linked", extra_payload={"issues_ids": list(issues_ids)}
    )
    assert_message_in_log(caplog, "Issues linked")


async def test_link_issues_dismiss_acknowledge(
    caplog, mocker, monkeypatch, sample_monitor: Monitor
):
    """'Alert.link_issues' should dismiss the alert's acknowledge if the attribute
    'dismiss_acknowledge_on_new_issues' is 'True' and issues are linked to the alert"""
    caplog.set_level(logging.DEBUG)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(
        dismiss_acknowledge_on_new_issues=True, rule=AgeRule(priority_levels=PriorityLevels())
    )
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
    )
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
            )
            for i in range(5)
        ]
    )

    alert_dismiss_acknowledge_spy: AsyncMock = mocker.spy(alert, "dismiss_acknowledge")

    assert alert.acknowledged

    await alert.link_issues(issues)

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.acknowledged
    alert_dismiss_acknowledge_spy.assert_awaited_once()


async def test_link_issues_no_dismiss_acknowledge(
    caplog, mocker, monkeypatch, sample_monitor: Monitor
):
    """'Alert.link_issues' should link the issues to the alert if all the necessary conditions
    are met"""
    caplog.set_level(logging.DEBUG)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    alert_options = AlertOptions(
        dismiss_acknowledge_on_new_issues=False, rule=AgeRule(priority_levels=PriorityLevels())
    )
    monkeypatch.setattr(monitor_code, "alert_options", alert_options, raising=False)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
    )
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
            )
            for i in range(5)
        ]
    )

    alert_dismiss_acknowledge_spy: MagicMock = mocker.spy(alert, "dismiss_acknowledge")

    assert alert.acknowledged

    await alert.link_issues(issues)

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged
    alert_dismiss_acknowledge_spy.assert_not_called()


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_acknowledge_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.acknowledge' should not acknowledge the alert if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.acknowledged
    assert loaded_alert.acknowledge_priority is None

    assert_message_in_log(caplog, f"Can't acknowledge, status is '{alert_status.value}'")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Acknowledged")


async def test_acknowledge_already_acknowledged(caplog, mocker, sample_monitor: Monitor):
    """'Alert.acknowledge' should not acknowledge the alert if it's already acknowledged"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=PriorityLevels.high,
        acknowledge_priority=AlertPriority.high,
        acknowledged=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged
    assert loaded_alert.acknowledge_priority == AlertPriority.high

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Acknowledged")


@pytest.mark.parametrize("priority", priority_utils.AlertPriority)
async def test_acknowledge_acknowledged(caplog, mocker, sample_monitor: Monitor, priority):
    """'Alert.acknowledge' should acknowledge the alert if all conditions are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=priority,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert not alert.acknowledged
    assert alert.acknowledge_priority is None

    await alert.acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged
    assert loaded_alert.acknowledge_priority == priority

    alert_create_event_spy.assert_awaited_once_with("alert_acknowledged")
    assert_message_in_log(caplog, "Acknowledged")


async def test_acknowledge_already_acknowledged_lower_priority(
    caplog, mocker, sample_monitor: Monitor
):
    """'Alert.acknowledge' should acknowledge the alert if it's already acknowledged but at a lower
    priority"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
        priority=AlertPriority.high,
        acknowledge_priority=AlertPriority.moderate,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert alert.acknowledged

    await alert.acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged
    assert loaded_alert.acknowledge_priority == AlertPriority.high

    alert_create_event_spy.assert_awaited_once_with("alert_acknowledged")
    assert_message_in_log(caplog, "Acknowledged")


async def test_acknowledge_acknowledged_not_send_event(caplog, mocker, sample_monitor: Monitor):
    """'Alert.acknowledge' should not create an event if the 'send_event' parameter is 'False'"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=priority_utils.AlertPriority.high,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert not alert.acknowledged
    assert alert.acknowledge_priority is None

    await alert.acknowledge(send_event=False)

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged
    assert loaded_alert.acknowledge_priority == priority_utils.AlertPriority.high

    alert_create_event_spy.assert_not_called()
    assert_message_in_log(caplog, "Acknowledged")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_dismiss_acknowledge_not_active(
    caplog, mocker, sample_monitor: Monitor, alert_status
):
    """'Alert.dismiss_acknowledge' should not dismiss the alert's acknowledgement if it's not
    active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
        acknowledged=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.dismiss_acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.acknowledged

    assert_message_in_log(caplog, f"Can't dismiss acknowledge, status is '{alert_status.value}'")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Acknowledgement dismissed")


async def test_dismiss_acknowledge_not_acknowledged(caplog, mocker, sample_monitor: Monitor):
    """'Alert.dismiss_acknowledge' should not dismiss the alert's acknowledgement if it's not
    acknowledged"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=False,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.dismiss_acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.acknowledged

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Acknowledgement dismissed")


async def test_dismiss_acknowledge_dismissed(caplog, mocker, sample_monitor: Monitor):
    """'Alert.dismiss_acknowledge' should dismiss the alert's acknowledgement if all conditions
    are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert alert.acknowledged

    await alert.dismiss_acknowledge()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.acknowledged

    alert_create_event_spy.assert_awaited_once_with("alert_acknowledge_dismissed")
    assert_message_in_log(caplog, "Acknowledgement dismissed")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_lock_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.lock' should not lock the alert if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.lock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.locked

    assert_message_in_log(caplog, f"Can't lock, status is '{alert_status.value}'")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Locked")


async def test_lock_already_locked(caplog, mocker, sample_monitor: Monitor):
    """'Alert.lock' should not lock the alert if it's already locked"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        locked=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.lock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.locked

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Locked")


async def test_lock_locked(caplog, mocker, sample_monitor: Monitor):
    """'Alert.lock' should lock the alert if all conditions are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert not alert.locked

    await alert.lock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.locked

    alert_create_event_spy.assert_awaited_once_with("alert_locked")
    assert_message_in_log(caplog, "Locked")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_unlock_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.unlock' should not unlock the alert if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
        locked=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.unlock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.locked

    assert_message_in_log(caplog, f"Can't unlock, status is '{alert_status.value}'")
    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Unlocked")


async def test_unlock_not_locked(caplog, mocker, sample_monitor: Monitor):
    """'Alert.unlock' should not unlock the alert if it's not locked"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.unlock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.locked

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Unlocked")


async def test_unlock_dismissed(caplog, mocker, sample_monitor: Monitor):
    """'Alert.unlock' should unlock the alert if all conditions are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        locked=True,
    )
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    assert alert.locked

    await alert.unlock()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert not loaded_alert.locked

    alert_create_event_spy.assert_awaited_once_with("alert_unlocked")
    assert_message_in_log(caplog, "Unlocked")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_update_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.update' should not update the alert if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )
    alert_solve_spy: MagicMock = mocker.spy(alert, "solve")
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.solved

    assert_message_in_log(caplog, f"Can't update, status is '{alert_status.value}'")
    alert_solve_spy.assert_not_called()
    alert_create_event_spy.assert_not_called()


async def test_update_solved(caplog, mocker, sample_monitor: Monitor):
    """'Alert.update' should solve the alert if there're no active issues linked to it"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
                status=IssueStatus.solved,
            )
            for i in range(5)
        ]
    )

    alert_solve_spy: MagicMock = mocker.spy(alert, "solve")
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.solved

    alert_solve_spy.assert_called_once()
    alert_create_event_spy.assert_awaited_once_with("alert_solved")
    assert_message_not_in_log(caplog, "Updated")


async def test_update_not_solved(caplog, mocker, sample_monitor: Monitor):
    """'Alert.update' should update the alert if there're active issues linked to it"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    alert_solve_spy: MagicMock = mocker.spy(alert, "solve")
    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.update()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.active

    alert_solve_spy.assert_not_called()
    alert_create_event_spy.assert_awaited_once_with("alert_updated")
    assert_message_in_log(caplog, "Updated")


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_solve_issues_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.solve_issues' should not solve the alert's issues if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )

    alert_acknowledge_spy: MagicMock = mocker.spy(alert, "acknowledge")
    alert_update_spy: MagicMock = mocker.spy(alert, "update")

    await alert.solve_issues()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == alert_status

    assert_message_in_log(caplog, f"Can't solve issues, status is '{alert_status.value}'")
    alert_acknowledge_spy.assert_not_called()
    alert_update_spy.assert_not_called()


async def test_solve_issues_solvable(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'Alert.solve_issues' should not solve the alert's issues if the issue options is configured
    as solvable"""
    caplog.set_level(logging.DEBUG)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    issue_options = IssueOptions(model_id_key="id", solvable=True)
    monkeypatch.setattr(monitor_code, "issue_options", issue_options)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    alert_acknowledge_spy: MagicMock = mocker.spy(alert, "acknowledge")
    alert_update_spy: MagicMock = mocker.spy(alert, "update")

    await alert.solve_issues()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.active

    solved_issues = await Issue.get_all(
        Issue.alert_id == alert.id, Issue.status == IssueStatus.solved
    )
    assert len(solved_issues) == 0

    assert_message_in_log(caplog, "Tried to solve an alert with solvable issues, skipping")
    alert_acknowledge_spy.assert_not_called()
    alert_update_spy.assert_not_called()


async def test_solve_issues_not_solvable(caplog, mocker, monkeypatch, sample_monitor: Monitor):
    """'Alert.solve_issues' should solve the alert's issues if the issue options is configured as
    not solvable"""
    caplog.set_level(logging.DEBUG)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    issue_options = IssueOptions(model_id_key="id", solvable=False)
    monkeypatch.setattr(monitor_code, "issue_options", issue_options)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    alert_acknowledge_spy: MagicMock = mocker.spy(alert, "acknowledge")
    alert_update_spy: MagicMock = mocker.spy(alert, "update")

    await alert.solve_issues()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.solved

    solved_issues = await Issue.get_all(
        Issue.alert_id == alert.id, Issue.status == IssueStatus.solved
    )
    assert len(solved_issues) == 5

    alert_acknowledge_spy.assert_called_once()
    alert_update_spy.assert_called_once()


@pytest.mark.parametrize("alert_status", [AlertStatus.solved])
async def test_solve_not_active(caplog, mocker, sample_monitor: Monitor, alert_status):
    """'Alert.solve' should set itself as solved if it's not active"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
    )

    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.solve()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == alert_status

    alert_create_event_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Solved")


async def test_solve_solved(caplog, mocker, sample_monitor: Monitor):
    """'Alert.solve' should set itself as solved if all conditions are met"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)

    alert_create_event_spy: AsyncMock = mocker.spy(alert, "_create_event")

    await alert.solve()

    loaded_alert = await Alert.get_by_id(alert.id)
    assert loaded_alert is not None
    assert loaded_alert.status == AlertStatus.solved
    assert loaded_alert.solved_at > time_utils.now() - timedelta(seconds=1)

    alert_create_event_spy.assert_awaited_once_with("alert_solved")
    assert_message_in_log(caplog, "Solved")

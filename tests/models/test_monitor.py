import inspect
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest.mock import MagicMock

import pytest

import databases.databases as databases
import utils.time as time_utils
from models import Alert, AlertStatus, Issue, IssueStatus, Monitor
from options import AlertOptions, CountRule, PriorityLevels, ReactionOptions
from registry import registry

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_monitor_id(sample_monitor: Monitor):
    """'Monitor.monitor_id' should have a property called 'monitor_id' that returns it's own id"""
    assert sample_monitor.monitor_id == sample_monitor.id


async def test_init_on_load(mocker, clear_database):
    """'init_on_load' should be called automatically when loading a monitor"""
    # As 'init_on_load' can't be mocked to check if it was called, the check will be that
    # '_post_create' was not called, which is the other way the variables are initialized
    _post_create_spy: MagicMock = mocker.spy(Monitor, "_post_create")

    await databases.execute_application(
        'insert into "Monitors"(id, name, enabled) values'
        "(9999123, 'monitor_1', true),"
        "(9999456, 'internal.monitor_2', true);"
    )

    monitor = await Monitor.get_by_id(9999123)

    assert monitor is not None

    _post_create_spy.assert_not_called()
    assert monitor.active_alerts == []
    assert monitor.active_issues == []


async def test_post_create():
    """'Monitor._post_create' should setup the monitor's internal variables"""
    class MonitorMock(ModuleType):
        pass

    assert registry._monitors == {}

    created_monitor = await Monitor.create(name="test_monitor_test_post_create")

    assert created_monitor.active_alerts == []
    assert created_monitor.active_issues == []


@pytest.mark.parametrize(
    "enabled, queued, running, last_execution, expected_result",
    [
        # Should not trigger if disabled
        (False, False, False, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        (False, True, False, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        (False, False, True, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        (False, True, True, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        # Should not trigger if running or queued
        (True, True, False, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        (True, False, True, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        # Should not trigger if disabled
        (False, False, False, None, False),
        (False, True, False, None, False),
        (False, False, True, None, False),
        (False, True, True, None, False),
        # Should not trigger if running or queued
        (True, True, False, None, False),
        (True, False, True, None, False),
        # Should not trigger if the cron isn't triggered according to the last execution
        (True, False, False, datetime(2024, 1, 1, 12, 34, 0, tzinfo=timezone.utc), False),
        # Should trigger if the last execution is None
        (True, False, False, None, True),
        # Should trigger if the cron is triggered according to the last execution
        (True, False, False, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), True),
    ],
)
async def test_is_triggered(
    monkeypatch, sample_monitor: Monitor, enabled, queued, running, last_execution, expected_result
):
    """'Monitor._is_triggered' should return if the provided 'cron' and 'last_execution'
    combination is considered triggered, if the monitor is not in a 'pending' state or disabled"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    sample_monitor.enabled = enabled
    sample_monitor.queued = queued
    sample_monitor.running = running

    result = sample_monitor._is_triggered("* * * * *", last_execution)

    assert result == expected_result


@pytest.mark.parametrize(
    "search_cron, search_executed_at, expected_result",
    [
        ("* * * * *", datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc), False),
        ("* * * * *", datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), True),
        (None, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 29, 59, tzinfo=timezone.utc), True),
        (None, datetime(2024, 1, 1, 12, 29, 59, tzinfo=timezone.utc), False),
    ],
)
async def test_is_search_triggered(
    monkeypatch, sample_monitor: Monitor, search_cron, search_executed_at, expected_result
):
    """'Monitor._is_search_triggered' should return if the search is triggered"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    sample_monitor.code.monitor_options.search_cron = search_cron
    sample_monitor.search_executed_at = search_executed_at

    result = sample_monitor.is_search_triggered

    assert result == expected_result


@pytest.mark.parametrize(
    "update_cron, update_executed_at, expected_result",
    [
        ("* * * * *", datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc), False),
        ("* * * * *", datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), True),
        (None, datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 33, 0, tzinfo=timezone.utc), False),
        ("*/5 * * * *", datetime(2024, 1, 1, 12, 29, 59, tzinfo=timezone.utc), True),
        (None, datetime(2024, 1, 1, 12, 29, 59, tzinfo=timezone.utc), False),
    ],
)
async def test_is_update_triggered(
    monkeypatch, sample_monitor: Monitor, update_cron, update_executed_at, expected_result
):
    """'Monitor._is_update_triggered' should return if the update is triggered"""
    monkeypatch.setattr(
        time_utils, "now", lambda: datetime(2024, 1, 1, 12, 34, 56, tzinfo=timezone.utc)
    )
    sample_monitor.code.monitor_options.update_cron = update_cron
    sample_monitor.update_executed_at = update_executed_at

    result = sample_monitor.is_update_triggered

    assert result == expected_result


async def test_code(sample_monitor: Monitor):
    """'Monitor.code' should return the monitor's code registered in the 'monitors' module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.code == monitor_code


async def test_options(sample_monitor: Monitor):
    """'Monitor.options' should return the monitor's 'monitor_options' from it's code module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.options == monitor_code.monitor_options


async def test_issue_options(sample_monitor: Monitor):
    """'Monitor.issue_options' should return the monitor's 'issue_options' from it's code module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.issue_options == monitor_code.issue_options


async def test_alert_options(sample_monitor: Monitor):
    """'Monitor.alert_options' should return the monitor's 'alert_options' from it's code module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monitor_code.alert_options = AlertOptions(rule=CountRule(priority_levels=PriorityLevels()))
    assert sample_monitor.alert_options == monitor_code.alert_options


async def test_alert_options_none(sample_monitor: Monitor):
    """'Monitor.alert_options' should return 'None' if the monitor's 'alert_options' isn't
    defined"""
    error_message = "has no attribute 'alert_options'"
    with pytest.raises(AttributeError, match=error_message):
        sample_monitor.code.alert_options

    assert sample_monitor.alert_options is None


async def test_reaction_options(sample_monitor: Monitor):
    """'Monitor.reaction_options' should return the monitor's 'reaction_options' from it's code
    module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monitor_code.reaction_options = ReactionOptions()
    assert sample_monitor.reaction_options == monitor_code.reaction_options


async def test_reaction_options_none(sample_monitor: Monitor):
    """'Monitor.reaction_options' should return an empty 'ReactionOptions()' object if the
    monitor's 'reaction_options" isn't defined"""
    error_message = "has no attribute 'reaction_options'"
    with pytest.raises(AttributeError, match=error_message):
        sample_monitor.code.reaction_options

    reaction_options = sample_monitor.reaction_options
    assert isinstance(reaction_options, ReactionOptions)

    for field in ReactionOptions.__dataclass_fields__:
        assert reaction_options[field] == []


async def test_search_function(sample_monitor: Monitor):
    """'Monitor.search_function' should return the monitor's 'search' function from it's code
    module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.search_function == monitor_code.search


async def test_update_function(sample_monitor: Monitor):
    """'Monitor.update_function' should return the monitor's 'update' function from it's code
    module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.update_function == monitor_code.update


async def test_is_solved_function(sample_monitor: Monitor):
    """'Monitor.is_solved_function' should return the monitor's 'is_solved' from it's code module"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    assert sample_monitor.is_solved_function == monitor_code.is_solved
    assert sample_monitor.is_solved_function.__name__ != "<lambda>"


async def test_is_solved_function_none(sample_monitor: Monitor):
    """'Monitor.is_solved_function' should return a lambda that always returns 'False' if the
    'is_solved' function isn't defined"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]

    del monitor_code.is_solved
    error_message = "has no attribute 'is_solved'"
    with pytest.raises(AttributeError, match=error_message):
        sample_monitor.code.is_solved

    assert inspect.isfunction(sample_monitor.is_solved_function)
    assert sample_monitor.is_solved_function.__name__ == "<lambda>"
    assert sample_monitor.is_solved_function("issue_data") is False


@pytest.mark.parametrize("number_of_issues", [1, 2, 5, 10])
async def test_load_active_issues(sample_monitor: Monitor, number_of_issues):
    """'Monitor.load_active_issues' should load all the monitor's active issues from the database
    and store them in the 'active_issues' attribute"""
    created_active_issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i}
            )
            for i in range(number_of_issues)
        ]
    )
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                status=IssueStatus.solved,
                data={"id": i},
            )
            for i in range(number_of_issues)
        ]
    )

    await sample_monitor.load_active_issues()
    issues_ids = {issue.id for issue in sample_monitor.active_issues}
    active_issues_ids = {issue.id for issue in created_active_issues}

    assert issues_ids == active_issues_ids


@pytest.mark.parametrize("number_of_alerts", [1, 2, 5, 10])
async def test_load_active_alerts(sample_monitor: Monitor, number_of_alerts):
    """'Monitor.load_active_alerts' should load all the monitor's active alerts from the database
    and store them in the 'active_alerts' attribute"""
    created_active_alerts = await Alert.create_batch(
        [
            Alert(monitor_id=sample_monitor.id)
            for i in range(number_of_alerts)
        ]
    )
    await Alert.create_batch(
        [
            Alert(
                monitor_id=sample_monitor.id,
                status=AlertStatus.solved,
            )
            for i in range(number_of_alerts)
        ]
    )

    await sample_monitor.load_active_alerts()
    alerts_ids = {alert.id for alert in sample_monitor.active_alerts}
    active_alerts_ids = {alert.id for alert in created_active_alerts}

    assert alerts_ids == active_alerts_ids


async def test_load(mocker, sample_monitor: Monitor):
    """'Monitor.loas' should load all module's active issues and alerts"""
    load_active_issues_spy = mocker.spy(sample_monitor, "load_active_issues")
    load_active_alerts_spy = mocker.spy(sample_monitor, "load_active_alerts")

    await sample_monitor.load()

    load_active_issues_spy.assert_called_once()
    load_active_alerts_spy.assert_called_once()


async def test_set_search_executed_at(sample_monitor: Monitor):
    """'Monitor.set_search_executed_at' should set the monitor's 'search_executed_at' to the
    current timestamp"""
    assert sample_monitor.search_executed_at is None
    sample_monitor.set_search_executed_at()
    assert sample_monitor.search_executed_at > time_utils.now() - timedelta(milliseconds=1)


async def test_set_update_executed_at(sample_monitor: Monitor):
    """'Monitor.set_update_executed_at' should set the monitor's 'update_executed_at' to the
    current timestamp"""
    assert sample_monitor.update_executed_at is None
    sample_monitor.set_update_executed_at()
    assert sample_monitor.update_executed_at > time_utils.now() - timedelta(milliseconds=1)


async def test_set_enabled(sample_monitor: Monitor):
    """'Monitor.set_enabled' should set the monitor's 'enabled' to the provided value"""
    await sample_monitor.set_enabled(True)
    assert sample_monitor.enabled is True
    await sample_monitor.set_enabled(True)
    assert sample_monitor.enabled is True
    await sample_monitor.set_enabled(False)
    assert sample_monitor.enabled is False
    await sample_monitor.set_enabled(False)
    assert sample_monitor.enabled is False


async def test_set_queued(sample_monitor: Monitor):
    """'Monitor.set_queued' should set the monitor's 'queued' to the provided value"""
    sample_monitor.set_queued(True)
    assert sample_monitor.queued is True
    queued_at = sample_monitor.queued_at

    sample_monitor.set_queued(True)
    assert sample_monitor.queued is True
    queued_at_2 = sample_monitor.queued_at
    assert queued_at_2 > queued_at

    sample_monitor.set_queued(False)
    assert sample_monitor.queued is False
    assert sample_monitor.queued_at == queued_at_2

    sample_monitor.set_queued(False)
    assert sample_monitor.queued is False
    assert sample_monitor.queued_at == queued_at_2


async def test_set_running(sample_monitor: Monitor):
    """'Monitor.set_running' should set the monitor's 'running' to the provided value"""
    sample_monitor.set_running(True)
    assert sample_monitor.running is True
    running_at = sample_monitor.running_at

    sample_monitor.set_running(True)
    assert sample_monitor.running is True
    running_at_2 = sample_monitor.running_at
    assert running_at_2 > running_at

    sample_monitor.set_running(False)
    assert sample_monitor.running is False
    assert sample_monitor.running_at == running_at_2

    sample_monitor.set_running(False)
    assert sample_monitor.running is False
    assert sample_monitor.running_at == running_at_2


async def test_add_issues_single(sample_monitor: Monitor):
    """'Monitor.add_issues' should add a provided Issue to the monitor's active issues list,
    keeping the items that were previously in the list"""
    created_issues = await Issue.create_batch(
        [
            Issue(monitor_id=sample_monitor.id, model_id="1", data={"id": 1}),
            Issue(monitor_id=sample_monitor.id, model_id="2", data={"id": 2}),
        ]
    )
    sample_monitor.active_issues = [created_issues[0]]
    sample_monitor.add_issues(created_issues[1])

    issues_ids = {issue.id for issue in sample_monitor.active_issues}
    active_issues_ids = {issue.id for issue in created_issues}

    assert issues_ids == active_issues_ids


async def test_add_issues_multiple(sample_monitor: Monitor):
    """'Monitor.add_issues' should add a provided list of Issues to the monitor's active issues
    list, keeping the items that were previously in the list"""
    created_issues = await Issue.create_batch(
        [
            Issue(monitor_id=sample_monitor.id, model_id="1", data={"id": 1}),
            Issue(monitor_id=sample_monitor.id, model_id="2", data={"id": 2}),
            Issue(monitor_id=sample_monitor.id, model_id="3", data={"id": 3}),
            Issue(monitor_id=sample_monitor.id, model_id="4", data={"id": 4}),
        ]
    )
    sample_monitor.active_issues = created_issues[0:2]
    sample_monitor.add_issues(created_issues[2:])

    issues_ids = {issue.id for issue in sample_monitor.active_issues}
    active_issues_ids = {issue.id for issue in created_issues}

    assert issues_ids == active_issues_ids


async def test_add_alert(sample_monitor: Monitor):
    """'Monitor.add_alerts' should add a provided Alert to the monitor's active alerts list,
    keeping the items that were previously in the list"""
    created_alerts = await Alert.create_batch([
        Alert(monitor_id=sample_monitor.id),
        Alert(monitor_id=sample_monitor.id)
    ])

    sample_monitor.active_alerts = [created_alerts[0]]
    sample_monitor.add_alert(created_alerts[1])

    alerts = {alert.id for alert in sample_monitor.active_alerts}
    active_alerts = {alert.id for alert in created_alerts}

    assert alerts == active_alerts


async def test_clear(sample_monitor: Monitor):
    """'Monitor.clear' should clear the monitor's 'active_issues' and 'active_alerts' lists"""
    sample_monitor.active_issues = [
        Issue(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})
    ]
    sample_monitor.active_alerts = [Alert(monitor_id=sample_monitor.id)]

    sample_monitor.clear()

    assert sample_monitor.active_issues == []
    assert sample_monitor.active_alerts == []

import asyncio
import logging
import math
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

import message_queue as message_queue
import utils.time as time_utils
from configs import configs
from data_models.event_payload import EventPayload
from data_models.monitor_options import ReactionOptions
from databases.databases import execute_application
from internal_database import get_session
from models import Alert, Issue, IssueStatus, Monitor
from registry import registry
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def do_nothing(): ...


# To test the Base class other models will be used, because most of the methods will make
# operations on the internal database, so there must be a table for it


async def test_should_queue_event_no_reaction_options(sample_monitor: Monitor):
    """'Base._should_queue_event' should return 'False' if the monitor has no 'reaction_options'
    setting"""
    with pytest.raises(AttributeError):
        sample_monitor.code.reaction_options

    assert sample_monitor._should_queue_event("alert_created") is False


@pytest.mark.parametrize(
    "event_name",
    [
        "not_an_event",
        "nothing_happened",
        "invalid_event",
    ],
)
async def test_should_queue_event_invalid_event(monkeypatch, sample_monitor: Monitor, event_name):
    """'Base._should_queue_event' should return 'False' if the event name is invalid"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(
        monitor_code,
        "reaction_options",
        ReactionOptions(alert_created=[do_nothing]),
        raising=False,
    )

    assert sample_monitor._should_queue_event(event_name) is False


@pytest.mark.parametrize(
    "event_name",
    [
        "alert_created",
        "issue_created",
        "issue_dropped",
        "notification_created",
    ],
)
async def test_should_queue_event(monkeypatch, sample_monitor: Monitor, event_name):
    """'Base._should_queue_event' should test if the event should be queued, based on the monitor's
    'reaction_options' settings"""
    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(
        monitor_code,
        "reaction_options",
        ReactionOptions(**{event_name: [do_nothing]}),
        raising=False,
    )

    assert sample_monitor._should_queue_event(event_name) is True
    assert sample_monitor._should_queue_event("alert_acknowledged") is False


async def test_build_event_payload(sample_monitor: Monitor):
    """'Base._build_event_payload' should build the payload for the event correctly"""
    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )

    payload = issue._build_event_payload("issue_created", {"test": 123})

    assert payload == {
        "event_source": "issue",
        "event_source_id": issue.id,
        "event_source_monitor_id": issue.monitor_id,
        "event_name": "issue_created",
        "event_data": {
            "id": issue.id,
            "monitor_id": issue.monitor_id,
            "alert_id": None,
            "model_id": "1",
            "status": "active",
            "data": {"id": 1},
            "created_at": issue.created_at.isoformat(),
            "solved_at": None,
            "dropped_at": None,
        },
        "extra_payload": {"test": 123},
    }
    assert EventPayload(**payload) is not None


@pytest.mark.parametrize(
    "event_name, extra_payload",
    [
        ("alert_created", None),
        ("issue_created", {}),
        ("issue_dropped", {"test": 123}),
    ],
)
async def test_create_event_queued(
    caplog, mocker, monkeypatch, sample_monitor: Monitor, event_name, extra_payload
):
    """'Base._create_event' should check if the event should be queued and queue them when true"""
    monkeypatch.setattr(configs, "log_all_events", True)

    monitor_code = registry._monitors[sample_monitor.id]["module"]
    monkeypatch.setattr(
        monitor_code,
        "reaction_options",
        ReactionOptions(**{event_name: [do_nothing]}),
        raising=False,
    )

    build_event_payload_spy: MagicMock = mocker.spy(sample_monitor, "_build_event_payload")
    build_event_payload_spy.return_value = {"some_event": "some_data"}
    should_queue_event_spy: MagicMock = mocker.spy(sample_monitor, "_should_queue_event")
    queue_send_message_spy: MagicMock = mocker.spy(message_queue, "send_message")

    await sample_monitor._create_event(event_name, extra_payload)

    build_event_payload_spy.assert_called_once_with(event_name, extra_payload)
    should_queue_event_spy.assert_called_once_with(event_name)
    queue_send_message_spy.assert_called_once_with(
        type="event", payload=sample_monitor._build_event_payload(event_name, extra_payload)
    )

    assert_message_in_log(caplog, f'"event_source_monitor_id": {sample_monitor.id}')
    assert_message_in_log(caplog, f'"event_name": "{event_name}"')


@pytest.mark.parametrize(
    "event_name, extra_payload",
    [
        ("alert_created", None),
        ("issue_created", {}),
        ("issue_dropped", {"test": 123}),
    ],
)
async def test_create_event_not_queued(mocker, sample_monitor: Monitor, event_name, extra_payload):
    """'Base._create_event' should check if the event should be queued and not queue them when
    false"""
    build_event_payload_spy: MagicMock = mocker.spy(sample_monitor, "_build_event_payload")
    build_event_payload_spy.return_value = {"some_event": "some_data"}
    should_queue_event_spy: MagicMock = mocker.spy(sample_monitor, "_should_queue_event")
    queue_send_message_spy: MagicMock = mocker.spy(message_queue, "send_message")

    await sample_monitor._create_event(event_name, extra_payload)

    build_event_payload_spy.assert_called_once_with(event_name, extra_payload)
    should_queue_event_spy.assert_called_once_with(event_name)
    queue_send_message_spy.assert_not_called()


@pytest.mark.parametrize(
    "event_name, extra_payload",
    [
        ("alert_created", None),
        ("issue_created", {}),
        ("issue_dropped", {"test": 123}),
    ],
)
async def test_create_event_not_queued_logged(
    caplog, mocker, monkeypatch, sample_monitor: Monitor, event_name, extra_payload
):
    """'Base._create_event' should lof the event when the 'log_all_events' setting is enabled, even
    if the event was not queued"""
    monkeypatch.setattr(configs, "log_all_events", True)

    build_event_payload_spy: MagicMock = mocker.spy(sample_monitor, "_build_event_payload")
    build_event_payload_spy.return_value = {"some_event": "some_data"}
    should_queue_event_spy: MagicMock = mocker.spy(sample_monitor, "_should_queue_event")
    queue_send_message_spy: MagicMock = mocker.spy(message_queue, "send_message")

    await sample_monitor._create_event(event_name, extra_payload)

    build_event_payload_spy.assert_called_once_with(event_name, extra_payload)
    should_queue_event_spy.assert_called_once_with(event_name)
    queue_send_message_spy.assert_not_called()

    assert_message_in_log(caplog, f'"event_source_monitor_id": {sample_monitor.id}')
    assert_message_in_log(caplog, f'"event_name": "{event_name}"')


async def test_logger(sample_monitor: Monitor):
    """'Base._logger' should lazy load a 'Logger' object"""
    with pytest.raises(AttributeError):
        sample_monitor._logger_obj

    assert isinstance(sample_monitor._logger, logging.Logger)

    assert sample_monitor._logger is not None
    assert sample_monitor._logger == sample_monitor._logger_obj


async def test_semaphore(sample_monitor: Monitor):
    """'Base._semaphore' should lazy load a 'Semaphore' object"""
    with pytest.raises(AttributeError):
        sample_monitor._semaphore_obj

    assert isinstance(sample_monitor._semaphore, asyncio.Semaphore)

    assert sample_monitor._semaphore is not None
    assert sample_monitor._semaphore == sample_monitor._semaphore_obj


@pytest.mark.parametrize("size", range(5))
async def test_count(sample_monitor: Monitor, size):
    """'Base.count' should return the number of objects in the database that match the
    provided parameters"""
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                status=IssueStatus.active if i % 2 == 0 else IssueStatus.dropped,
            )
            for i in range(size)
        ]
    )

    assert await Issue.count(Issue.monitor_id == sample_monitor.id) == size
    active_issues = await Issue.count(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.active
    )
    assert active_issues == math.ceil(size / 2)
    dropped_issues = await Issue.count(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.dropped
    )
    assert dropped_issues == math.floor(size / 2)


@pytest.mark.parametrize("size", range(5))
async def test_create_batch(mocker, sample_monitor: Monitor, size):
    """'Base.create_batch' should create a list of instances in the database, call their
    '_post_create' methods and queue the creation events for them"""
    issues_to_create = [
        Issue(
            monitor_id=sample_monitor.id,
            model_id=str(i),
            data={"id": i},
        )
        for i in range(size)
    ]

    post_create_spies: list[MagicMock] = []
    create_event_spies: list[MagicMock] = []
    for issue in issues_to_create:
        post_create_spies.append(mocker.spy(issue, "_post_create"))
        create_event_spies.append(mocker.spy(issue, "_create_event"))

    await Issue.create_batch(issues_to_create)

    for issue in await Issue.get_all(Issue.monitor_id == sample_monitor.id):
        assert issue.id is not None
    for post_create_spy in post_create_spies:
        post_create_spy.assert_called_once()
    for create_event_spy in create_event_spies:
        create_event_spy.assert_called_once_with("issue_created")


async def test_create(mocker, sample_monitor: Monitor):
    """'Base.create' should create an instance in the database, call it's '_post_create' method and
    queue the creation event for it"""
    post_create_spy = mocker.spy(Issue, "_post_create")
    create_event_spy = mocker.spy(Issue, "_create_event")

    issue = await Issue.create(
        monitor_id=sample_monitor.id,
        model_id="1",
        data={"id": 1},
    )

    assert issue.id is not None
    post_create_spy.assert_called_once()
    create_event_spy.assert_called_once_with(issue, "issue_created")


async def test_get(sample_monitor: Monitor):
    """'Base.get' should get a single instance that matches the provided filters, or 'None' if
    none was found"""
    found_monitor = await Monitor.get(Monitor.id == sample_monitor.id)
    assert found_monitor is not None
    assert isinstance(found_monitor, Monitor)
    assert found_monitor.id == sample_monitor.id

    not_found_monitor = await Monitor.get(Monitor.name == "a monitor that doesn't exists")
    assert not_found_monitor is None


async def test_get_raw(sample_monitor: Monitor):
    """'Base.get_raw' should return a list of dictionaries with the raw information for the
    provided columns that match the provided filters"""
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                status=IssueStatus.active,
            )
            for i in range(3)
        ]
    )
    issues_data = {issue.id: (issue.model_id, issue.data) for issue in issues}

    found_issues = await Issue.get_raw(
        columns=[Issue.id, Issue.model_id, Issue.data],
        column_filters=[Issue.monitor_id == sample_monitor.id],
    )
    found_issues_data = {issue[0]: (issue[1], issue[2]) for issue in found_issues}
    assert found_issues_data == issues_data


async def test_get_raw_no_filters(sample_monitor: Monitor):
    """'Base.get_raw' should return a list of dictionaries with the raw information for the
    provided columns when no filters are provided"""
    found_issues = await Issue.get_raw(
        columns=[Issue.id, Issue.model_id, Issue.data],
    )
    assert len(found_issues) >= 3


async def test_get_raw_not_found(sample_monitor: Monitor):
    """'Base.get_raw' should return an empty list if no instances were found"""
    not_found_issues = await Issue.get_raw(
        columns=[Issue.id, Issue.model_id, Issue.data],
        column_filters=[Issue.id == -1],
    )
    assert not_found_issues == []


async def test_get_by_id(sample_monitor: Monitor):
    """'Base.get_by_id' should get a single instance that has the provided 'id' or None if none was
    found"""
    found_monitor = await Monitor.get_by_id(sample_monitor.id)
    assert found_monitor is not None
    assert isinstance(found_monitor, Monitor)
    assert found_monitor.id == sample_monitor.id

    not_found_monitor = await Monitor.get_by_id(-1)
    assert not_found_monitor is None


async def test_get_all(sample_monitor: Monitor):
    """'Base.get_all' should return all instances that match the the provided filters"""
    active_issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                status=IssueStatus.active,
            )
            for i in range(3)
        ]
    )
    active_issues_ids = {issue.id for issue in active_issues}

    dropped_issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(5 + i),
                data={"id": 5 + i},
                status=IssueStatus.dropped,
            )
            for i in range(3)
        ]
    )
    dropped_issues_ids = {issue.id for issue in dropped_issues}

    issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id)
    issues_ids = {issue.id for issue in issues}
    assert issues_ids == active_issues_ids | dropped_issues_ids


async def test_get_all_order_by(sample_monitor: Monitor):
    """'Base.get_all' should return all instances that match the the provided filters, sorted by the
    provided columns"""
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                status=IssueStatus.active,
            )
            for i in range(3)
        ]
    )

    issues_ids = sorted([issue.id for issue in issues])

    sorted_issues = await Issue.get_all(Issue.monitor_id == sample_monitor.id, order_by=[Issue.id])
    sorted_issues_ids = [issue.id for issue in sorted_issues]

    sorted_issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id,
        order_by=[Issue.id.desc()],
    )
    sorted_issues_ids = [issue.id for issue in sorted_issues]
    assert sorted_issues_ids == list(reversed(issues_ids))


async def test_get_all_limit(sample_monitor: Monitor):
    """'Base.get_all' should return all instances that match the the provided filters, limited by
    the provided number"""
    issues = await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                status=IssueStatus.active,
            )
            for i in range(3)
        ]
    )

    issues_ids = sorted([issue.id for issue in issues])

    limited_issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id,
        order_by=[Issue.id],
        limit=2,
    )
    limited_issues_ids = [issue.id for issue in limited_issues]
    assert len(limited_issues) == 2
    assert limited_issues_ids == issues_ids[:2]

    sorted_issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id,
        order_by=[Issue.id.desc()],
        limit=2,
    )
    sorted_issues_ids = [issue.id for issue in sorted_issues]
    assert sorted_issues_ids == list(reversed(issues_ids[-2:]))


async def test_get_or_create(sample_monitor: Monitor):
    """'Base.get_or_create' should try to get an instance that matches the the provided filters and
    if none was found, try to create it"""
    alert = await Alert.get(Alert.monitor_id == sample_monitor.id)
    assert alert is None

    created_alert = await Alert.get_or_create(monitor_id=sample_monitor.id)
    assert created_alert is not None

    loaded_alert = await Alert.get_or_create(monitor_id=sample_monitor.id)
    assert loaded_alert is not None
    assert loaded_alert.id == created_alert.id


async def test_refresh(sample_monitor: Monitor):
    """'Base.refresh' should reload the instance attributes from the database"""
    query = (
        'update "Monitors" set '
        "enabled = false, "
        "search_executed_at = current_timestamp, "
        "update_executed_at = current_timestamp, "
        "queued = true, "
        "running = true "
        f"where id = {sample_monitor.id};"
    )
    await execute_application(query)

    assert sample_monitor.enabled is True
    assert sample_monitor.search_executed_at is None
    assert sample_monitor.update_executed_at is None
    assert sample_monitor.queued is False
    assert sample_monitor.running is False

    await sample_monitor.refresh()

    assert sample_monitor.enabled is False
    assert sample_monitor.search_executed_at is not None
    assert sample_monitor.update_executed_at is not None
    assert sample_monitor.queued is True
    assert sample_monitor.running is True


async def test_save_without_session(sample_monitor: Monitor):
    """'Base.save' should save the instance to the database creating a session, while also adding
    the callback, if provided"""
    assert sample_monitor.search_executed_at is None
    sample_monitor.search_executed_at = time_utils.now()

    callback = AsyncMock()

    await sample_monitor.save(callback=callback())

    count = await Monitor.count(
        Monitor.id == sample_monitor.id,
        Monitor.search_executed_at.is_(None),
    )
    assert count == 0

    monitor = await Monitor.get(Monitor.id == sample_monitor.id)
    assert monitor.search_executed_at > time_utils.now() - timedelta(seconds=1)
    callback.assert_awaited_once()


async def test_save_with_session(sample_monitor: Monitor):
    """'Base.save' should save the instance to the database using the provided session, while also
    adding the callback, if provided"""
    assert sample_monitor.search_executed_at is None

    callback = AsyncMock()

    async with get_session() as session:
        sample_monitor.search_executed_at = time_utils.now()
        await sample_monitor.save(session=session, callback=callback())

        count = await Monitor.count(
            Monitor.id == sample_monitor.id,
            Monitor.search_executed_at.is_(None),
        )

        assert count == 1
        callback.assert_not_awaited()

    count = await Monitor.count(
        Monitor.id == sample_monitor.id,
        Monitor.search_executed_at.is_(None),
    )
    assert count == 0

    monitor = await Monitor.get(Monitor.id == sample_monitor.id)
    assert monitor.search_executed_at > time_utils.now() - timedelta(seconds=1)
    callback.assert_awaited_once()

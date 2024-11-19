from unittest.mock import AsyncMock, MagicMock

import pytest

from src.internal_database import get_session
from src.models import Issue, IssueStatus, Monitor
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("number_of_callbacks", [1, 3, 5])
async def test_callbacks(mocker, number_of_callbacks, sample_monitor: Monitor):
    """'get_session' should execute all the callback functions after the commit"""
    async def do_nothing(): ...

    callback_mock = AsyncMock(side_effect=do_nothing)

    async with get_session() as session:
        execute_callbacks_spy: MagicMock = mocker.spy(session, "execute_callbacks")

        sample_monitor.enabled = False
        session.add(sample_monitor)

        for _ in range(number_of_callbacks):
            session.add_callback(callback_mock())

        monitor = await Monitor.get_by_id(sample_monitor.id)
        assert monitor is not None
        assert monitor.enabled

        execute_callbacks_spy.assert_not_called()
        callback_mock.assert_not_awaited()

    execute_callbacks_spy.assert_called_once()

    # Monitor should've been updated
    monitor = await Monitor.get_by_id(sample_monitor.id)
    assert monitor is not None
    assert not monitor.enabled

    assert callback_mock.await_count == number_of_callbacks


async def test_callbacks_error(caplog, mocker, sample_monitor: Monitor):
    """'get_session' should not execute any of the callbacks and should cancel all callbacks
    coroutines if there's an error while the session is open"""
    async def callback_error():
        raise TypeError("callback error")

    callback_mock = AsyncMock(side_effect=callback_error)

    # Stores the monitor id in a variable
    # When there's an error in the middle of a transaction, the objects attached to it will become
    # detached and, then, not possible to access it's attributes
    monitor_id = sample_monitor.id

    counter = 0
    with pytest.raises(ValueError, match="commit error"):
        async with get_session() as session:
            execute_callbacks_spy: MagicMock = mocker.spy(session, "execute_callbacks")
            cancel_callbacks_spy: MagicMock = mocker.spy(session, "cancel_callbacks")

            sample_monitor.enabled = False
            session.add(sample_monitor)

            for _ in range(5):
                session.add_callback(callback_mock())
                counter += 1

            raise ValueError("commit error")

    # 5 callbacks should've been queued
    assert counter == 5

    # Monitor shouldn't have been updated
    monitor = await Monitor.get_by_id(monitor_id)
    assert monitor is not None
    assert monitor.enabled

    execute_callbacks_spy.assert_not_called()
    cancel_callbacks_spy.assert_called_once()
    callback_mock.assert_not_awaited()
    assert_message_not_in_log(caplog, "callback error")


async def test_callbacks_callback_error(caplog, mocker, sample_monitor: Monitor):
    """'get_session' should execute all the callbacks even if some of them raises exceptions"""
    async def callback_error():
        raise TypeError("callback error")

    callback_mock = AsyncMock(side_effect=callback_error)

    counter = 0
    async with get_session() as session:
        execute_callbacks_spy: MagicMock = mocker.spy(session, "execute_callbacks")
        cancel_callbacks_spy: MagicMock = mocker.spy(session, "cancel_callbacks")

        sample_monitor.enabled = False
        session.add(sample_monitor)

        for _ in range(5):
            session.add_callback(callback_mock())
            counter += 1

    # 5 callbacks should've been queued
    assert counter == 5

    # Monitor should've been updated
    monitor = await Monitor.get_by_id(sample_monitor.id)
    assert monitor is not None
    assert not monitor.enabled

    execute_callbacks_spy.assert_called_once()
    cancel_callbacks_spy.assert_not_called()
    assert callback_mock.await_count == 5
    assert_message_in_log(caplog, "TypeError: callback error", count=5)


async def test_bulk_execute(mocker, sample_monitor: Monitor):
    """'get_session should return a session that will execute all operations in the database in a
    single transaction and should execute all the callbacks after the commit"""
    async def do_nothing(): ...

    callback_mock = AsyncMock(side_effect=do_nothing)

    issues: list[Issue] = [
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id="1",
            data={"id": 1, "value": 1},
        ),
        await Issue.create(
            monitor_id=sample_monitor.id,
            model_id="2",
            data={"id": 2, "value": 2},
        ),
    ]

    async with get_session() as session:
        execute_callbacks_spy: MagicMock = mocker.spy(session, "execute_callbacks")

        for issue in issues:
            issue.status = IssueStatus.solved
        session.add_all(issues)

        for _ in range(5):
            session.add_callback(callback_mock())

        solved_issues = await Issue.get_all(
            Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.solved
        )
        assert len(solved_issues) == 0

        execute_callbacks_spy.assert_not_called()
        callback_mock.assert_not_awaited()

    execute_callbacks_spy.assert_called_once()

    solved_issues = await Issue.get_all(
        Issue.monitor_id == sample_monitor.id, Issue.status == IssueStatus.solved
    )
    assert len(solved_issues) == 2

    assert callback_mock.await_count == 5

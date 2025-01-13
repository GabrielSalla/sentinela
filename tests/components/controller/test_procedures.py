from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import components.controller.procedures as procedures
from configs import configs
from models import Monitor
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


def get_time(reference: str) -> datetime | None:
    values = {
        "now": datetime.now(),
        "five_minutes_ago": datetime.now() - timedelta(seconds=301),
    }
    return values.get(reference)


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("queued", [False, True])
@pytest.mark.parametrize("running", [False, True])
@pytest.mark.parametrize("queued_at", [None, "now", "five_minutes_ago"])
@pytest.mark.parametrize("running_at", [None, "now", "five_minutes_ago"])
async def test_monitors_stuck(
    caplog,
    sample_monitor: Monitor,
    enabled,
    queued,
    running,
    queued_at,
    running_at,
):
    """'_monitors_stuck' should fix monitors that are stuck"""
    sample_monitor.enabled = enabled
    sample_monitor.queued = queued
    sample_monitor.running = running
    sample_monitor.queued_at = get_time(queued_at)  # type:ignore[assignment]
    sample_monitor.running_at = get_time(running_at)  # type:ignore[assignment]
    await sample_monitor.save()

    await procedures._monitors_stuck()

    await sample_monitor.refresh()

    if not enabled:
        triggered = False
    elif queued_at is None and running_at is None:
        triggered = False
    elif queued_at == "now" or running_at == "now":
        triggered = False
    else:
        triggered = (queued or running)

    if triggered:
        assert not sample_monitor.queued
        assert not sample_monitor.running
        assert_message_in_log(
            caplog, f"monitors_stuck: {sample_monitor} was stuck and now it's fixed"
        )
    else:
        assert sample_monitor.queued == queued
        assert sample_monitor.running == running
        assert_message_not_in_log(
            caplog, f"monitors_stuck: {sample_monitor} was stuck and now it's fixed"
        )


async def test_monitors_stuck_query_result_none(caplog, monkeypatch):
    """'_monitors_stuck' should log an error if the query result is None"""
    monkeypatch.setattr(
        procedures.databases, "query_application", AsyncMock(return_value=None)
    )

    await procedures._monitors_stuck()

    assert_message_in_log(caplog, "monitors_stuck: Error with query result")


async def test_monitors_stuck_monitor_not_found(caplog, monkeypatch):
    """'_monitors_stuck' should log an error if the monitor is not found"""
    monkeypatch.setattr(
        procedures.databases,
        "query_application",
        AsyncMock(return_value=[{"id": 99999999}])
    )

    await procedures._monitors_stuck()

    assert_message_in_log(caplog, "Monitor with id '99999999' not found")


async def test_monitors_stuck_monitor_not_found_2_results(
    caplog,
    monkeypatch,
    sample_monitor: Monitor
):
    """'_monitors_stuck' should log an error if one monitor is not found but should continue with
    the other monitors"""
    monkeypatch.setattr(
        procedures.databases,
        "query_application",
        AsyncMock(return_value=[{"id": 99999999}, {"id": sample_monitor.id}])
    )

    await procedures._monitors_stuck()

    assert_message_in_log(caplog, "Monitor with id '99999999' not found")
    assert_message_in_log(
        caplog, f"monitors_stuck: {sample_monitor} was stuck and now it's fixed"
    )


@pytest.mark.parametrize("last_execution, is_triggered, expected_result", [
    (None, True, True),
    (None, False, True),
    ("not None", True, True),
    ("not None", False, False),
])
async def test_check_procedure_triggered(
    monkeypatch,
    last_execution,
    is_triggered,
    expected_result,
):
    """'_check_procedure_triggered' should return if the procedure is triggered"""
    monkeypatch.setattr(procedures, "is_triggered", lambda *args: is_triggered)

    result = procedures._check_procedure_triggered(
        schedule="", last_execution=last_execution
    )

    assert result == expected_result


async def test_execute_procedure(monkeypatch):
    """'_execute_procedure' should execute the procedure and update the last_executions"""
    monkeypatch.setattr(procedures, "last_executions", {})
    procedure_mock = AsyncMock()

    await procedures._execute_procedure("procedure", procedure_mock)

    procedure_mock.assert_awaited_once()
    assert isinstance(procedures.last_executions["procedure"], datetime)
    assert procedures.last_executions["procedure"] > datetime.now() - timedelta(seconds=1)


async def test_execute_procedure_error(caplog, monkeypatch):
    """'_execute_procedure' should catch exceptions and log them"""
    monkeypatch.setattr(procedures, "last_executions", {})
    procedure_mock = AsyncMock(side_effect=Exception("Some error"))

    await procedures._execute_procedure("procedure", procedure_mock)

    procedure_mock.assert_awaited_once()
    assert isinstance(procedures.last_executions["procedure"], datetime)
    assert procedures.last_executions["procedure"] > datetime.now() - timedelta(seconds=1)
    assert_message_in_log(caplog, "Exception: Some error")


async def test_run_procedures(monkeypatch):
    """'run_procedures' should run all procedures that are triggered"""
    procedure1_mock = AsyncMock()
    procedure2_mock = AsyncMock()
    monkeypatch.setattr(
        procedures,
        "procedures",
        {"some_procedure": procedure1_mock, "other_procedure": procedure2_mock},
    )
    monkeypatch.setattr(procedures, "last_executions", {})
    monkeypatch.setattr(
        configs,
        "controller_procedures", {
            "some_procedure": {"schedule": "* * * * *"},
            "other_procedure": {"schedule": "* * * * *"},
        }
    )

    await procedures.run_procedures()

    procedure1_mock.assert_awaited_once()
    procedure2_mock.assert_awaited_once()

    assert isinstance(procedures.last_executions["some_procedure"], datetime)
    assert isinstance(procedures.last_executions["other_procedure"], datetime)

    assert procedures.last_executions["some_procedure"] > datetime.now() - timedelta(seconds=1)
    assert procedures.last_executions["other_procedure"] > datetime.now() - timedelta(seconds=1)


async def test_run_procedures_error(caplog, monkeypatch):
    """'run_procedures' should run all procedures that are triggered even if they have errors"""
    procedure1_mock = AsyncMock(side_effect=Exception("Some error"))
    procedure2_mock = AsyncMock()
    monkeypatch.setattr(
        procedures,
        "procedures",
        {"some_procedure": procedure1_mock, "other_procedure": procedure2_mock},
    )
    monkeypatch.setattr(procedures, "last_executions", {})
    monkeypatch.setattr(
        configs,
        "controller_procedures", {
            "some_procedure": {"schedule": "* * * * *"},
            "other_procedure": {"schedule": "* * * * *"},
        }
    )

    await procedures.run_procedures()

    procedure1_mock.assert_awaited_once()
    procedure2_mock.assert_awaited_once()

    assert isinstance(procedures.last_executions["some_procedure"], datetime)
    assert isinstance(procedures.last_executions["other_procedure"], datetime)

    assert procedures.last_executions["some_procedure"] > datetime.now() - timedelta(seconds=1)
    assert procedures.last_executions["other_procedure"] > datetime.now() - timedelta(seconds=1)

    assert_message_in_log(caplog, "Exception: Some error")

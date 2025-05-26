from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import components.controller.run_procedures as run_procedures
from configs import ControllerProcedureConfig, configs
from tests.test_utils import assert_message_in_log
from utils.time import now

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "last_execution, is_triggered, expected_result",
    [
        (None, True, True),
        (None, False, True),
        ("not None", True, True),
        ("not None", False, False),
    ],
)
async def test_check_procedure_triggered(
    monkeypatch,
    last_execution,
    is_triggered,
    expected_result,
):
    """'_check_procedure_triggered' should return if the procedure is triggered"""
    monkeypatch.setattr(run_procedures, "is_triggered", lambda *args: is_triggered)

    result = run_procedures._check_procedure_triggered(schedule="", last_execution=last_execution)

    assert result == expected_result


async def test_execute_procedure(monkeypatch):
    """'_execute_procedure' should execute the procedure and update the last_executions"""
    monkeypatch.setattr(run_procedures, "last_executions", {})
    procedure_mock = AsyncMock()

    await run_procedures._execute_procedure("procedure", procedure_mock, {"param": "value"})

    procedure_mock.assert_awaited_once_with(param="value")
    assert isinstance(run_procedures.last_executions["procedure"], datetime)
    assert run_procedures.last_executions["procedure"] > now() - timedelta(seconds=1)


async def test_execute_procedure_error(caplog, monkeypatch):
    """'_execute_procedure' should catch exceptions and log them"""
    monkeypatch.setattr(run_procedures, "last_executions", {})
    procedure_mock = AsyncMock(side_effect=Exception("Some error"))

    await run_procedures._execute_procedure("procedure", procedure_mock, {"param": "value"})

    procedure_mock.assert_awaited_once()
    assert isinstance(run_procedures.last_executions["procedure"], datetime)
    assert run_procedures.last_executions["procedure"] > now() - timedelta(seconds=1)
    assert_message_in_log(caplog, "Exception: Some error")


async def test_run_procedures(monkeypatch):
    """'run_procedures' should run all procedures that are triggered"""
    procedure1_mock = AsyncMock()
    procedure2_mock = AsyncMock()
    monkeypatch.setattr(
        run_procedures,
        "procedures",
        {"some_procedure": procedure1_mock, "other_procedure": procedure2_mock},
    )
    monkeypatch.setattr(run_procedures, "last_executions", {})
    monkeypatch.setattr(
        configs,
        "controller_procedures",
        {
            "some_procedure": ControllerProcedureConfig(schedule="* * * * *"),
            "other_procedure": ControllerProcedureConfig(schedule="* * * * *"),
        },
    )

    await run_procedures.run_procedures()

    procedure1_mock.assert_awaited_once()
    procedure2_mock.assert_awaited_once()

    assert isinstance(run_procedures.last_executions["some_procedure"], datetime)
    assert isinstance(run_procedures.last_executions["other_procedure"], datetime)

    assert run_procedures.last_executions["some_procedure"] > now() - timedelta(seconds=1)
    assert run_procedures.last_executions["other_procedure"] > now() - timedelta(seconds=1)


async def test_run_procedures_error(caplog, monkeypatch):
    """'run_procedures' should run all procedures that are triggered even if they have errors"""
    procedure1_mock = AsyncMock(side_effect=Exception("Some error"))
    procedure2_mock = AsyncMock()
    monkeypatch.setattr(
        run_procedures,
        "procedures",
        {"some_procedure": procedure1_mock, "other_procedure": procedure2_mock},
    )
    monkeypatch.setattr(run_procedures, "last_executions", {})
    monkeypatch.setattr(
        configs,
        "controller_procedures",
        {
            "some_procedure": ControllerProcedureConfig(schedule="* * * * *"),
            "other_procedure": ControllerProcedureConfig(schedule="* * * * *"),
        },
    )

    await run_procedures.run_procedures()

    procedure1_mock.assert_awaited_once_with()
    procedure2_mock.assert_awaited_once_with()

    assert isinstance(run_procedures.last_executions["some_procedure"], datetime)
    assert isinstance(run_procedures.last_executions["other_procedure"], datetime)

    assert run_procedures.last_executions["some_procedure"] > now() - timedelta(seconds=1)
    assert run_procedures.last_executions["other_procedure"] > now() - timedelta(seconds=1)

    assert_message_in_log(caplog, "Exception: Some error")

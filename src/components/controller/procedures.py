"""Procedures are a way to run some checks periodically to make sure everything is working as
expected.
An example of a procedure is to check if there are any monitors that are stuck in the 'processing'
state for too long. It can happen if the monitor execution is abruptly interrupted, and the
execution doesn't complete properly. If this happens, the monitor won't be processed again."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Coroutine

import databases
from configs import configs
from models import Monitor
from utils.exception_handling import catch_exceptions
from utils.time import is_triggered, now

_logger = logging.getLogger("controller_procedures")

SQL_FILES_PATH = Path(__file__).parent / "sql_files"


async def _monitors_stuck(time_tolerance: int) -> None:
    with open(SQL_FILES_PATH / "monitors_stuck.sql") as file:
        query = file.read()

    result = await databases.query_application(query, time_tolerance)

    if result is None:
        _logger.error("monitors_stuck: Error with query result")
        return

    for monitor_info in result:
        monitor = await Monitor.get_by_id(monitor_info["id"])

        if monitor is None:
            _logger.error(f"monitors_stuck: Monitor with id '{monitor_info['id']}' not found")
            continue

        monitor.set_queued(False)
        monitor.set_running(False)
        await monitor.save()

        _logger.warning(f"monitors_stuck: {monitor} was stuck and now it's fixed")


procedures: dict[str, Callable[..., Coroutine[None, None, None]]] = {
    "monitors_stuck": _monitors_stuck,
}

last_executions: dict[str, datetime] = {}


def _check_procedure_triggered(schedule: str, last_execution: datetime | None) -> bool:
    """Check if the procedure is triggered based on the 'schedule' and 'last_execution'
    variables"""
    if last_execution is None:
        return True

    return is_triggered(schedule, last_execution)


async def _execute_procedure(
    procedure_name: str,
    procedure: Callable[[], Coroutine[None, None, None]],
    procedure_settings: dict[str, str | int | float | bool | None],
) -> None:
    """Execute the 'procedure' and update the 'last_executions' variable"""
    with catch_exceptions(logger=_logger):
        await procedure(**procedure_settings)
    last_executions[procedure_name] = now()


async def run_procedures() -> None:
    """Check and run all procedures that are triggered"""
    for procedure_name, procedure in procedures.items():
        procedure_settings = configs.controller_procedures[procedure_name]

        last_execution = last_executions.get(procedure_name)
        procedure_triggered = _check_procedure_triggered(
            procedure_settings.schedule, last_execution
        )

        if procedure_triggered:
            procedure_params = getattr(procedure_settings, "params", None) or {}
            await _execute_procedure(procedure_name, procedure, procedure_params)

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import message_queue as message_queue
import registry as registry
import utils.app as app
from configs import configs
from utils.exception_handling import catch_exceptions
from utils.time import format_datetime_iso, now, time_since

from .runner import Runner

TASKS_FINISH_CHECK_TIME = 1

_logger = logging.getLogger("executor")

last_message_at: datetime
running: bool = False
started_at: datetime = now()


async def diagnostics() -> tuple[dict[str, Any], list[str]]:
    """Get the Executor's diagnostics information for reporting"""
    status: dict[str, Any] = {}
    issues: list[str] = []

    time_since_started = time_since(started_at)
    if time_since_started != -1 and time_since_started < 60:
        return status, issues

    status["last_message_at"] = format_datetime_iso(last_message_at)
    time_since_last_message = time_since(last_message_at)
    if time_since_last_message == -1 or time_since_last_message > 300:
        issues.append("no_recent_messages")

    return status, issues


def count_running(tasks: list[asyncio.Task[Any]]) -> int:
    """Count the number of running tasks"""
    return len([task for task in tasks if not task.done()])


async def wait_for_tasks(tasks: list[asyncio.Task[Any]]) -> None:
    """Wait for all running tasks to finish"""
    while count_running(tasks) > 0:
        _logger.info(f"Waiting for {count_running(tasks)} tasks to finish")
        await asyncio.sleep(TASKS_FINISH_CHECK_TIME)


async def run() -> None:
    global last_message_at
    global running

    tasks: list[asyncio.Task[Any]] = []
    runner_id = 0
    running = True
    semaphore = asyncio.Semaphore(configs.executor_concurrency)

    _logger.info("Executor running")

    while app.running():
        with catch_exceptions(_logger):
            # Tasks cleaning
            tasks = [task for task in tasks if not task.done()]

            async with semaphore:
                message = await message_queue.get_message()

            if message is None:
                await app.sleep(configs.executor_sleep)
                continue

            last_message_at = now()

            runner_id += 1
            runner = Runner(runner_id, message)
            runner_task = asyncio.create_task(runner.process(semaphore))
            tasks.append(runner_task)

            # Give control back to the event loop
            await asyncio.sleep(0)

    _logger.info("Finishing")
    await wait_for_tasks(tasks)

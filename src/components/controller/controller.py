import asyncio
import logging
import traceback
from datetime import datetime
from typing import Any

import prometheus_client

import message_queue as message_queue
import registry as registry
import utils.app as app
from configs import configs
from models import Monitor
from utils.exception_handling import catch_exceptions
from utils.time import format_datetime_iso, is_triggered, now, time_since, time_until_next_trigger

from .procedures import run_procedures

_logger = logging.getLogger("controller")

running: bool = False
started_at: datetime = now()
last_loop_at: datetime
last_monitor_processed_at: datetime

prometheus_monitors_processed_count = prometheus_client.Counter(
    "controller_monitors_processed_count", "Count of monitors processed by the controller"
)
prometheus_monitor_not_registered_count = prometheus_client.Counter(
    "controller_monitor_not_registered_count",
    "Count of times the controller tries to process a monitor that isn't registered",
)
prometheus_task_queue_error_count = prometheus_client.Counter(
    "controller_task_queue_error_count",
    "Count of times the controller fails to queue a task",
)


async def diagnostics() -> tuple[dict[str, Any], list[str]]:
    """Get the Controller's diagnostics information for reporting"""
    status: dict[str, Any] = {}
    issues: list[str] = []

    time_since_started = time_since(started_at)
    if time_since_started != -1 and time_since_started < 60:
        return status, issues

    status["last_loop_at"] = format_datetime_iso(last_loop_at)
    time_since_last_loop = time_since(last_loop_at)
    if time_since_last_loop == -1 or time_since_last_loop > 300:
        issues.append("loop_not_running")

    status["last_monitor_processed_at"] = format_datetime_iso(last_monitor_processed_at)
    time_since_last_monitor_processed = time_since(last_monitor_processed_at)
    if time_since_last_monitor_processed == -1 or time_since_last_monitor_processed > 300:
        issues.append("no_recent_monitor_processed")

    return status, issues


async def _queue_task(monitor: Monitor, tasks: list[str]) -> None:
    """Send a message to the queue with the monitor tasks that should be executed"""
    monitor.set_queued(True)
    await monitor.save()

    try:
        await message_queue.send_message(
            type="process_monitor",
            payload={
                "monitor_id": monitor.id,
                "tasks": tasks,
            },
        )
    except Exception:
        prometheus_task_queue_error_count.inc()

        _logger.error("Error while queueing the task, reverting queued state")
        _logger.error(traceback.format_exc().strip())
        monitor.set_queued(False)
        await monitor.save()


async def _process_monitor(monitor: Monitor) -> None:
    """Check if the monitor triggers any task and queue them if there're any"""
    global last_monitor_processed_at

    prometheus_monitors_processed_count.inc()

    tasks: list[str] = []

    search_triggered = monitor.is_search_triggered
    if search_triggered:
        tasks.append("search")

    update_triggered = monitor.is_update_triggered
    if update_triggered:
        tasks.append("update")

    last_monitor_processed_at = now()

    if not tasks:
        return

    _logger.info(f"Triggered {tasks} for {monitor}")

    await _queue_task(monitor, tasks)


async def _run_task(semaphore: asyncio.Semaphore, monitor: Monitor) -> None:
    """Keep one of the semaphore's lock while the monitor is being processed"""
    _logger.info(f"Processing monitor {monitor}")
    async with semaphore:
        await _process_monitor(monitor)


async def _create_process_task(
    semaphore: asyncio.Semaphore, monitor: Monitor
) -> asyncio.Task[Any] | None:
    """Create a task to process the monitor"""
    # Instead of registering the monitor, skip if it's not registered yet
    # If processing a monitor that is not yet registered, the executor won't have
    # the monitor's module available
    if not registry.is_monitor_registered(monitor.id):
        prometheus_monitor_not_registered_count.inc()
        _logger.warning(f"Monitor {monitor} is not registered, skipping")
        return None

    # Process monitors concurrently
    # Use '_run_task' to keep the semaphore lock while the monitor is being processed
    async with semaphore:
        return asyncio.create_task(_run_task(semaphore, monitor))


async def run() -> None:
    global last_loop_at
    global running

    running = True

    _logger.info("Controller running")

    # Load configs
    controller_process_schedule = configs.controller_process_schedule

    # Queue setup
    semaphore = asyncio.Semaphore(configs.controller_concurrency)

    tasks: list[asyncio.Task[Any]] = []

    while app.running():
        with catch_exceptions(_logger):
            # Wait for monitors to be ready
            await registry.wait_monitors_ready()

            # Tasks cleaning
            tasks = [task for task in tasks if not task.done()]

            last_loop_at = now()

            # Run the procedures in the background
            procedures_task = asyncio.create_task(run_procedures())
            tasks.append(procedures_task)

            # Loop through all monitors
            enabled_monitors = await Monitor.get_all(Monitor.enabled.is_(True))
            for monitor in enabled_monitors:
                task = await _create_process_task(semaphore, monitor)
                if task is not None:
                    tasks.append(task)

        # Sleep until next scheduling decision, if necessary
        if not is_triggered(controller_process_schedule, last_loop_at):
            sleep_time = time_until_next_trigger(controller_process_schedule)
            await app.sleep(sleep_time)

    _logger.info("Finishing")

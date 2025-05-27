import asyncio
import logging
from functools import partial
from typing import Any, Coroutine

import utils.app as app
from utils.exception_handling import protected_task

TASKS_FINISH_CHECK_TIME = 1
LOOP_TIME = 60

_logger = logging.getLogger("task_manager")

_tasks: dict[asyncio.Task[Any] | None, list[asyncio.Task[Any]]] = {}


def _on_parent_done(parent_task: asyncio.Task[Any], task: asyncio.Task[Any]) -> None:
    """Callback when parent task is done to cancel child task if it's still running"""
    if not task.done():
        _logger.error(f"Cancelling task '{task.get_name()}' as parent task is done")
        task.cancel()


def create_task(
    coro: Coroutine[Any, Any, Any], parent_task: asyncio.Task[Any] | None = None
) -> asyncio.Task[Any]:
    """Create a task that will be executed in the background with an optional 'parent' attribute. If
    the parent task is done while the child task is running, the child task will be canceled"""
    task = asyncio.create_task(protected_task(_logger, coro), name=coro.__name__)
    _tasks.setdefault(parent_task, []).append(task)

    if parent_task is not None:
        parent_task.add_done_callback(partial(_on_parent_done, task=task))

    return task


def _clear_completed() -> None:
    """Remove completed tasks from the global task list"""
    global _tasks

    cleaned_tasks = {}

    for parent, tasks in _tasks.items():
        active_tasks = [task for task in tasks if not task.done()]
        if len(active_tasks) > 0:
            cleaned_tasks[parent] = active_tasks

    _tasks = cleaned_tasks


async def wait_for_tasks(
    parent_task: asyncio.Task[Any] | None, timeout: float | None = None, cancel: bool = False
) -> bool:
    """Wait for all running tasks started by the parent task to finish. If all tasks finish before
    the timeout, the function will return True. If the timeout is 'None', the function will wait
    until all tasks finish. If the timeout is reached, the function will return False.
    If cancel is True, all pending tasks will be cancelled on timeout."""
    tasks = _tasks.get(parent_task, [])
    if len(tasks) == 0:
        return True

    done, pending = await asyncio.wait(tasks, timeout=timeout)

    if len(pending) > 0:
        if cancel:
            for task in pending:
                _logger.info(f"Task '{task.get_name()}' timed out")
                task.cancel()
        return False

    return True


def _count_running(tasks: dict[Any, list[asyncio.Task[Any]]]) -> int:
    """Count the number of running tasks"""
    running_tasks = 0
    for task_list in tasks.values():
        running_tasks += len([task for task in task_list if not task.done()])
    return running_tasks


async def _wait_to_finish(tasks: dict[Any, list[asyncio.Task[Any]]]) -> None:
    """Wait for all running tasks to finish"""
    while True:
        running_tasks = _count_running(tasks)
        if running_tasks == 0:
            break
        _logger.info(f"Waiting for {running_tasks} tasks to finish")
        await asyncio.sleep(TASKS_FINISH_CHECK_TIME)


async def run() -> None:
    _logger.info("Task manager running")

    while app.running():
        _clear_completed()
        await app.sleep(LOOP_TIME)

    _logger.info("Finishing")
    await _wait_to_finish(_tasks)

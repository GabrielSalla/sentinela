import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

import components.task_manager.task_manager as task_manager
import utils.app as app
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture(loop_scope="session", scope="function", autouse=True)
async def setup():
    """Reset task manager state before each test"""
    for tasks in task_manager._tasks.values():
        for task in tasks:
            task.cancel()

    task_manager._tasks.clear()


@pytest.fixture(scope="module", autouse=True)
def cancel_tasks_after_test(monkeypatch_module):
    """Cancel all the created tasks to prevent pending tasks at the end of the test session"""
    asyncio_create_task = asyncio.create_task
    created_tasks = []

    def create_task(*args, **kwargs):
        task = asyncio_create_task(*args, **kwargs)
        created_tasks.append(task)
        return task

    monkeypatch_module.setattr(asyncio, "create_task", create_task)

    yield

    for task in created_tasks:
        if not task.done():
            task.cancel()


async def test_on_parent_done_no_cancel(caplog):
    """'_on_parent_done' should not try to cancel the child tasks when the parent task is done and
    it's not running"""
    parent_task = asyncio.create_task(asyncio.sleep(0.05))
    task = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task)

    await parent_task

    assert task.done()
    assert_message_not_in_log(caplog, "Cancelling task")

    await parent_task


async def test_on_parent_done_cancel(caplog):
    """'_on_parent_done' should cancel child tasks when the parent task is done and it's still
    running"""
    parent_task = asyncio.create_task(asyncio.sleep(0))
    task = task_manager.create_task(asyncio.sleep(1), parent_task=parent_task)

    await parent_task
    await asyncio.sleep(0.1)

    assert_message_in_log(caplog, "Cancelling task 'sleep' as parent task is done")

    with pytest.raises(asyncio.CancelledError):
        await task

    await parent_task


async def test_create_task():
    """'create_task' should create a task and add it to the task manager belonging to the parent
    task"""
    parent_task_1 = None
    task_1 = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task_1)

    parent_task_2 = asyncio.create_task(asyncio.sleep(0))
    task_2 = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task_2)

    parent_task_3 = asyncio.create_task(asyncio.sleep(0))
    task_3 = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task_3)
    task_4 = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task_3)

    assert isinstance(task_1, asyncio.Task)
    assert isinstance(task_2, asyncio.Task)
    assert isinstance(task_3, asyncio.Task)
    assert isinstance(task_4, asyncio.Task)

    assert task_manager._tasks == {
        None: [task_1],
        parent_task_2: [task_2],
        parent_task_3: [task_3, task_4],
    }


async def test_clear_completed():
    """'_clear_completed' should remove completed tasks from the task manager"""
    parent_task_1 = asyncio.create_task(asyncio.sleep(0.2))
    task_1 = task_manager.create_task(asyncio.sleep(0), parent_task=parent_task_1)

    parent_task_2 = asyncio.create_task(asyncio.sleep(0.3))
    task_2 = task_manager.create_task(asyncio.sleep(0.1), parent_task=parent_task_2)
    task_3 = task_manager.create_task(asyncio.sleep(0.2), parent_task=parent_task_2)

    assert task_manager._tasks == {
        parent_task_1: [task_1],
        parent_task_2: [task_2, task_3],
    }

    await task_1
    task_manager._clear_completed()

    assert task_manager._tasks == {
        parent_task_2: [task_2, task_3],
    }

    await task_2
    task_manager._clear_completed()

    assert task_manager._tasks == {
        parent_task_2: [task_3],
    }

    await task_3
    task_manager._clear_completed()

    assert task_manager._tasks == {}


async def test_wait_for_tasks():
    """'wait_for_tasks' should wait for all tasks started by the parent task to finish"""
    parent_task_1 = asyncio.create_task(asyncio.sleep(0.3))
    task_1 = asyncio.create_task(asyncio.sleep(1))

    parent_task_2 = asyncio.create_task(asyncio.sleep(0.3))
    task_2 = asyncio.create_task(asyncio.sleep(1))
    task_3 = asyncio.create_task(asyncio.sleep(1))

    task_manager._tasks = {
        parent_task_1: [task_1],
        parent_task_2: [task_2, task_3],
    }

    wait_task_1 = asyncio.create_task(task_manager.wait_for_tasks(parent_task=parent_task_1))
    wait_task_2 = asyncio.create_task(task_manager.wait_for_tasks(parent_task=parent_task_2))

    await asyncio.sleep(0.05)
    assert not wait_task_1.done()
    assert not wait_task_2.done()

    task_1.cancel()
    await asyncio.sleep(0.05)

    assert wait_task_1.done()
    assert not wait_task_2.done()

    task_2.cancel()
    await asyncio.sleep(0.05)

    assert wait_task_1.done()
    assert not wait_task_2.done()

    task_3.cancel()
    await asyncio.sleep(0.05)

    assert wait_task_1.done()
    assert wait_task_2.done()

    assert await wait_task_1
    assert await wait_task_2


async def test_wait_for_tasks_timeout():
    """'wait_for_tasks' should wait for all tasks started by the parent task to finish, but
    timeout if they don't finish in time. The tasks should not be cancelled"""
    parent_task_1 = asyncio.create_task(asyncio.sleep(0.3))
    task_1 = asyncio.create_task(asyncio.sleep(1))

    parent_task_2 = asyncio.create_task(asyncio.sleep(0.3))
    task_2 = asyncio.create_task(asyncio.sleep(1))
    task_3 = asyncio.create_task(asyncio.sleep(1))

    task_manager._tasks = {
        parent_task_1: [task_1],
        parent_task_2: [task_2, task_3],
    }

    wait_task_1 = asyncio.create_task(
        task_manager.wait_for_tasks(parent_task=parent_task_1, timeout=0.1)
    )
    wait_task_2 = asyncio.create_task(
        task_manager.wait_for_tasks(parent_task=parent_task_2, timeout=0.2)
    )

    await asyncio.sleep(0.06)
    assert not wait_task_1.done()
    assert not wait_task_2.done()

    await asyncio.sleep(0.06)
    assert wait_task_1.done()
    assert not wait_task_2.done()

    await asyncio.sleep(0.1)
    assert wait_task_1.done()
    assert wait_task_2.done()

    assert not task_1.done()
    assert not task_2.done()
    assert not task_3.done()

    assert not await wait_task_1
    assert not await wait_task_2


async def test_wait_for_tasks_timeout_cancel(caplog):
    """'wait_for_tasks' should wait for all tasks started by the parent task to finish, but
    timeout if they don't finish in time. The tasks should be cancelled"""
    parent_task_1 = asyncio.create_task(asyncio.sleep(0.3))
    task_1 = asyncio.create_task(asyncio.sleep(1))
    task_1.set_name("task_1")

    parent_task_2 = asyncio.create_task(asyncio.sleep(0.3))
    task_2 = asyncio.create_task(asyncio.sleep(1))
    task_2.set_name("task_2")
    task_3 = asyncio.create_task(asyncio.sleep(1))
    task_3.set_name("task_3")

    task_manager._tasks = {
        parent_task_1: [task_1],
        parent_task_2: [task_2, task_3],
    }

    wait_task_1 = asyncio.create_task(
        task_manager.wait_for_tasks(parent_task=parent_task_1, timeout=0.1, cancel=True)
    )
    wait_task_2 = asyncio.create_task(
        task_manager.wait_for_tasks(parent_task=parent_task_2, timeout=0.2, cancel=True)
    )

    await asyncio.sleep(0.05)
    assert not wait_task_1.done()
    assert not wait_task_2.done()

    await asyncio.sleep(0.05)
    assert wait_task_1.done()
    assert_message_in_log(caplog, "Task 'task_1' timed out")
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task_1, timeout=0.1)
    assert not wait_task_2.done()
    assert not task_2.done()
    assert not task_3.done()

    await asyncio.sleep(0.1)
    assert wait_task_1.done()
    assert wait_task_2.done()
    assert_message_in_log(caplog, "Task 'task_2' timed out")
    assert_message_in_log(caplog, "Task 'task_3' timed out")
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task_2, timeout=0.1)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task_3, timeout=0.1)

    assert not await wait_task_1
    assert not await wait_task_2


async def test_wait_for_tasks_empty():
    """'wait_for_tasks' should return True if there are no tasks to wait for"""
    parent_task = asyncio.create_task(asyncio.sleep(0.3))
    task_manager._tasks = {parent_task: []}

    result = await asyncio.wait_for(
        task_manager.wait_for_tasks(parent_task=parent_task), timeout=0.1
    )
    assert result

    result = await asyncio.wait_for(
        task_manager.wait_for_tasks(parent_task="parent_task"), timeout=0.1
    )
    assert result


@pytest.mark.parametrize("timeout, cancel", [(0.1, False), (0.2, True)])
async def test_wait_for_all_tasks(mocker, timeout, cancel):
    """'wait_for_all_tasks' should wait for all tasks to finish, but timeout if they don't finish
    in time. The tasks should be cancelled if 'cancel' is True"""
    wait_for_tasks_spy: AsyncMock = mocker.spy(task_manager, "wait_for_tasks")

    parent_task_1 = asyncio.create_task(asyncio.sleep(0.3))
    task_1 = asyncio.create_task(asyncio.sleep(0.05))

    parent_task_2 = asyncio.create_task(asyncio.sleep(0.3))
    task_2 = asyncio.create_task(asyncio.sleep(0.05))
    task_3 = asyncio.create_task(asyncio.sleep(0.05))

    task_manager._tasks = {
        parent_task_1: [task_1],
        parent_task_2: [task_2, task_3],
    }

    await asyncio.wait_for(
        task_manager.wait_for_all_tasks(timeout=timeout, cancel=cancel),
        timeout=0.15,
    )

    assert wait_for_tasks_spy.await_count == 2
    assert wait_for_tasks_spy.await_args_list == [
        ((), {"parent_task": parent_task_1, "timeout": timeout, "cancel": cancel}),
        ((), {"parent_task": parent_task_2, "timeout": timeout, "cancel": cancel}),
    ]


async def test_wait_for_all_tasks_empty():
    """'wait_for_all_tasks' should return True if there are no tasks to wait for"""
    task_manager._tasks = {}
    await asyncio.wait_for(task_manager.wait_for_all_tasks(), timeout=0.1)
    await asyncio.wait_for(task_manager.wait_for_all_tasks(timeout=0.1), timeout=0.1)


@pytest.mark.parametrize("running_tasks", [0, 1, 2, 3, 4, 5])
async def test_count_running(running_tasks):
    """'count_running' should return the number of running tasks"""
    finished_tasks_1 = [asyncio.create_task(asyncio.sleep(0)) for i in range(running_tasks)]
    running_tasks_1 = [asyncio.create_task(asyncio.sleep(1)) for i in range(10 - running_tasks)]

    finished_tasks_2 = [asyncio.create_task(asyncio.sleep(0.2)) for i in range(2 * running_tasks)]
    running_tasks_2 = [asyncio.create_task(asyncio.sleep(1)) for i in range(10 - 2 * running_tasks)]

    all_tasks = {
        1: finished_tasks_1 + running_tasks_1,
        2: finished_tasks_2 + running_tasks_2,
    }

    result = task_manager._count_running(all_tasks)
    assert result == 20

    await asyncio.sleep(0.11)

    result = task_manager._count_running(all_tasks)
    assert result == 20 - running_tasks

    await asyncio.sleep(0.11)

    result = task_manager._count_running(all_tasks)
    assert result == 20 - running_tasks * 3


@pytest.mark.parametrize("tasks", [{}, {1: []}, {1: [], 2: []}])
async def test_count_running_empty(tasks):
    """'count_running' should return 0 when there are no tasks"""
    assert task_manager._count_running(tasks) == 0


async def test_wait_to_finish(caplog, monkeypatch):
    """'_wait_to_finish' should wait for all running tasks to finish"""
    monkeypatch.setattr(task_manager, "TASKS_FINISH_CHECK_TIME", 0.1)

    tasks = {i: [asyncio.create_task(asyncio.sleep(i / 10 - 0.05))] for i in range(1, 6)}

    await asyncio.wait_for(task_manager._wait_to_finish(tasks), timeout=0.6)
    assert_message_in_log(caplog, "Waiting for 5 tasks to finish")
    assert_message_in_log(caplog, "Waiting for 4 tasks to finish")
    assert_message_in_log(caplog, "Waiting for 3 tasks to finish")
    assert_message_in_log(caplog, "Waiting for 2 tasks to finish")
    assert_message_in_log(caplog, "Waiting for 1 tasks to finish")


async def test_wait_to_finish_empty():
    """'_wait_to_finish' should return immediately if there are no tasks to wait for"""
    await asyncio.wait_for(task_manager._wait_to_finish({}), timeout=0.1)


async def test_run(mocker):
    """'_run' should clear the completed tasks and wait for the remaining tasks to finish when the
    application is stopping"""
    clear_completed_spy: MagicMock = mocker.spy(task_manager, "_clear_completed")
    wait_to_finish_spy: AsyncMock = mocker.spy(task_manager, "_wait_to_finish")

    run_task = asyncio.create_task(task_manager.run())

    await asyncio.sleep(0.1)

    assert not run_task.done()
    clear_completed_spy.assert_called_once()
    wait_to_finish_spy.assert_not_called()

    app.stop()

    await asyncio.wait_for(run_task, timeout=0.1)

    wait_to_finish_spy.assert_called_once_with(task_manager._tasks)

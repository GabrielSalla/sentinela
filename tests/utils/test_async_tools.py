import asyncio
import time
from math import ceil

import pytest

from src.utils.async_tools import do_concurrently

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "task_number, size",
    [
        (1, 5),
        (5, 5),
        (6, 5),
        (2, 3),
        (3, 3),
        (4, 3),
    ],
)
async def test_do_concurrently(task_number, size):
    """'do_concurrently' should execute tasks concurrently, limited to the provided 'size'
    argument"""
    tasks = [asyncio.sleep(0.2) for _ in range(task_number)]
    start_time = time.perf_counter()
    await do_concurrently(*tasks, size=size)
    end_time = time.perf_counter()
    total_time = end_time - start_time

    assert total_time > 0.2 * ceil(task_number / size)
    assert total_time < 0.2 * ceil(task_number / size) + 0.005


async def test_do_concurrently_return_values():
    """'do_concurrently' should return a list of each of the task's returned values"""

    async def f(value):
        await asyncio.sleep(0.1)
        return value

    tasks = [f(i) for i in range(10)]
    result = await do_concurrently(*tasks)
    expected_result = list(range(10))

    assert result == expected_result


async def test_do_concurrently_error_single():
    """'do_concurrently' should handle errors in the tasks, without impacting others.
    Tasks with errors will have 'None' as return value"""

    async def no_error(i):
        await asyncio.sleep(0.2)
        return i

    async def error():
        await asyncio.sleep(0.2)
        raise ValueError("oh no")

    tasks = [
        no_error(1),
        no_error(2),
        error(),
        no_error(3),
        no_error(4),
    ]
    start_time = time.perf_counter()
    result = await do_concurrently(*tasks, size=5)
    end_time = time.perf_counter()
    total_time = end_time - start_time

    assert total_time > 0.2
    assert total_time < 0.2 + 0.005

    assert result == [1, 2, None, 3, 4]


async def test_do_concurrently_error_all():
    """'do_concurrently' should handle errors in the tasks, without impacting others.
    Tasks with errors will have 'None' as return value"""

    async def error():
        await asyncio.sleep(0.2)
        raise ValueError("oh no")

    tasks = [
        error(),
        error(),
        error(),
        error(),
        error(),
    ]
    start_time = time.perf_counter()
    result = await do_concurrently(*tasks, size=5)
    end_time = time.perf_counter()
    total_time = end_time - start_time

    assert total_time > 0.2
    assert total_time < 0.2 + 0.005

    assert result == [None] * 5

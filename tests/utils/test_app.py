import asyncio
import signal
import time

import pytest

import src.utils.app as app

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="function")
def set_signal_handlers():
    app.setup()
    yield
    app.remove_signal_handlers()


@pytest.mark.parametrize("seconds", [0, 0.1, 0.4, 0.5, 1])
async def test_sleep(seconds):
    """'sleep' should sleep for the correct amount of seconds"""
    start_time = time.perf_counter()
    await app.sleep(seconds)
    end_time = time.perf_counter()
    total_time = end_time - start_time
    assert total_time > seconds - 0.001
    assert total_time < seconds + 0.003


@pytest.mark.parametrize("seconds", [-10, -5, -0.001])
async def test_sleep_negative(seconds):
    """'sleep' should return instantly if the amount of seconds is negative"""
    start_time = time.perf_counter()
    await app.sleep(seconds)
    end_time = time.perf_counter()
    total_time = end_time - start_time
    assert total_time < 0.003


async def test_sleep_early_cancelling():
    """'sleep' should stop early if the task is cancelled"""
    start_time = time.perf_counter()

    task = asyncio.create_task(app.sleep(10))
    await asyncio.sleep(0.2)
    assert not task.done()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=0.5)

    end_time = time.perf_counter()
    total_time = end_time - start_time
    assert total_time > 0.2 - 0.001
    assert total_time < 0.2 + 0.003


async def test_sleep_early_stop_running():
    """'sleep' should stop before reaching the number of seconds if the app stopped"""
    start_time = time.perf_counter()

    task = asyncio.create_task(app.sleep(10))
    await asyncio.sleep(0.2)
    assert not task.done()

    app.stop()
    await asyncio.wait_for(task, timeout=0.5)

    end_time = time.perf_counter()
    total_time = end_time - start_time
    assert total_time > 0.2 - 0.001
    assert total_time < 0.2 + 0.003


@pytest.mark.parametrize("raise_signal", [signal.SIGINT, signal.SIGTERM])
async def test_signal_handling(set_signal_handlers, raise_signal):
    """'sleep' should stop if any of the signals registered are raised"""
    start_time = time.perf_counter()
    task = asyncio.create_task(app.sleep(10))
    await asyncio.sleep(0.2)
    assert not task.done()

    signal.raise_signal(raise_signal)
    await asyncio.wait_for(task, timeout=0.5)

    end_time = time.perf_counter()
    total_time = end_time - start_time
    assert total_time > 0.2 - 0.001
    assert total_time < 0.2 + 0.003

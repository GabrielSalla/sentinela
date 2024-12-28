import asyncio
import logging
from typing import Any, Awaitable

from utils.exception_handling import catch_exceptions

_logger = logging.getLogger("async_tools")


async def _run(semaphore: asyncio.Semaphore, task: Awaitable) -> Any:
    """Run a single task holding a lock in the semaphore. Catch and log any errors that might
    occur, protecting other tasks from breaking"""
    async with semaphore:
        with catch_exceptions(_logger):
            return await task


async def do_concurrently(*tasks: Awaitable[Any], size: int = 5) -> list[Any]:
    """Execute a list of awaitable objects concurrently, limited by the provided 'size' argument"""
    semaphore = asyncio.Semaphore(size)
    return await asyncio.gather(*[_run(semaphore, task) for task in tasks])

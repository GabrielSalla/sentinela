import asyncio
import logging
import traceback
from contextlib import contextmanager
from typing import Coroutine, Generator

from base_exception import BaseSentinelaException


@contextmanager
def catch_exceptions(
    logger: logging.Logger | None = None,
    error_message: str | None = None,
    timeout_message: str | None = None,
) -> Generator[None, None, None]:
    """Execute some code catching and logging any exceptions that might occur"""
    if logger is None:
        logger = logging.getLogger("exception_handler")

    try:
        yield
    except asyncio.TimeoutError:
        if timeout_message:
            logger.error(timeout_message)
    except BaseSentinelaException as e:
        logger.error(str(e))
    except Exception:
        logger.error(traceback.format_exc().strip())
        if error_message:
            logger.error(error_message)
        logger.info("Exception caught successfully, going on")


async def protected_task(logger: logging.Logger, task: Coroutine[None, None, None]) -> None:
    try:
        await task
    except Exception:
        logger.error(f"Exception with task '{task}'")
        logger.error(traceback.format_exc().strip())

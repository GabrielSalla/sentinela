import asyncio
import logging
from unittest.mock import MagicMock

import pytest

from src.base_exception import BaseSentinelaException
from src.utils.exception_handling import catch_exceptions
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_catch_exceptions_no_errors(caplog):
    """'catch_exceptions' should not log any message if the execution doesn't raise any errors"""
    with catch_exceptions(error_message="error", timeout_message="timeout"):
        await asyncio.sleep(0.1)

    assert_message_not_in_log(caplog, "error")
    assert_message_not_in_log(caplog, "timeout")
    assert_message_not_in_log(caplog, "Exception caught successfully, going on")


@pytest.mark.parametrize("logger", [None, logging.getLogger("some_logger")])
async def test_catch_exceptions_timeout(caplog, mocker, logger):
    """'catch_exceptions' should log the provided timeout error message with the provided logger,
    if not None, if a 'TimeoutError' exception is raised"""
    if logger is not None:
        logger_error_spy: MagicMock = mocker.spy(logger, "error")

    async def error():
        await asyncio.sleep(2)
        raise ValueError("should not be raised")

    with catch_exceptions(logger=logger, timeout_message="error function timed out"):
        await asyncio.wait_for(error(), timeout=0.1)

    assert_message_in_log(caplog, "error function timed out")
    assert_message_not_in_log(caplog, "should not be raised")

    if logger is not None:
        logger_error_spy.assert_called_once_with("error function timed out")


async def test_catch_exceptions_base_exception(caplog):
    """'catch_exceptions' should log the exception message if an exception inherited from
    'BaseSentinelaException' is raised"""
    class CustomException(BaseSentinelaException):
        pass

    with catch_exceptions():
        raise CustomException("should be raised")

    assert_message_in_log(caplog, "CustomException: should be raised")


@pytest.mark.parametrize("logger", [None, logging.getLogger("other_logger")])
async def test_catch_exceptions_error(caplog, mocker, logger):
    """'catch_exceptions' should log the provided error message with the provided logger, if not
    None, if any exception other than 'TimeoutError' is raised"""
    if logger is not None:
        logger_error_spy: MagicMock = mocker.spy(logger, "error")
        logger_info_spy: MagicMock = mocker.spy(logger, "info")

    async def error():
        await asyncio.sleep(0.1)
        raise ValueError("should be raised")

    with catch_exceptions(logger=logger, error_message="error function raised exception"):
        await error()

    assert_message_in_log(caplog, "error function raised exception")
    assert_message_in_log(caplog, "Exception caught successfully, going on")
    assert_message_in_log(caplog, "ValueError: should be raised")

    if logger is not None:
        assert logger_error_spy.call_count == 2
        logger_error_spy.assert_called_with("error function raised exception")
        logger_info_spy.assert_called_once_with("Exception caught successfully, going on")

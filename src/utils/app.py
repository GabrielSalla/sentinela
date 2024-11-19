import asyncio
import logging
import signal

_logger = logging.getLogger("app")
_stop_event = asyncio.Event()


def running() -> bool:
    return not _stop_event.is_set()


def stop():
    _stop_event.set()


def _stop(signal_name):
    """Stop the app when a signal is received"""
    _logger.info(f"Signal {signal_name} caught, finishing")
    stop()


def setup():
    """Setup the signal handlers for SIGINT and SIGTERM to stop the app"""
    _stop_event.clear()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, _stop, "SIGINT")
    loop.add_signal_handler(signal.SIGTERM, _stop, "SIGTERM")


def remove_signal_handlers():
    """Remove the signal handlers for SIGINT and SIGTERM"""
    loop = asyncio.get_event_loop()
    loop.remove_signal_handler(signal.SIGINT)
    loop.remove_signal_handler(signal.SIGTERM)


async def sleep(seconds: float):
    """Sleep for the specified amount of seconds in steps of 0.5 seconds. If the app is stopped,
    it will break prematurely"""
    if seconds <= 0:
        return

    done, pending = await asyncio.wait(
        [asyncio.create_task(_stop_event.wait())],
        timeout=seconds,
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()

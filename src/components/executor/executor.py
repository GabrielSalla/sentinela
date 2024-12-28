from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Coroutine

import prometheus_client

import message_queue as message_queue
import registry as registry
import utils.app as app
from base_exception import BaseSentinelaException
from configs import configs
from utils.exception_handling import catch_exceptions
from utils.time import format_datetime_iso, now, time_since

from . import monitor_handler, reaction_handler, request_handler

_logger = logging.getLogger("executor")

running: bool = False
started_at: datetime = now()
last_message_at: datetime
executors: list[Executor] = []

prometheus_message_count = prometheus_client.Counter(
    "executor_message_count", "Count of messages consumed by the executors", ["message_type"]
)
prometheus_message_error_count = prometheus_client.Counter(
    "executor_message_error_count", "Count of errors when processing messages", ["message_type"]
)
prometheus_message_processing_count = prometheus_client.Gauge(
    "executor_message_processing_count",
    "Count of messages being processed by the executors",
    ["message_type"],
)


async def diagnostics() -> tuple[dict[str, Any], list[str]]:
    """Get the Executor's diagnostics information for reporting"""
    status: dict[str, Any] = {}
    issues: list[str] = []

    status["executors_count"] = len(executors)
    if len(executors) < configs.executor_concurrency:
        issues.append("degraded_internal_executors")

    time_since_started = time_since(started_at)
    if time_since_started != -1 and time_since_started < 60:
        return status, issues

    status["last_message_at"] = format_datetime_iso(last_message_at)
    time_since_last_message = time_since(last_message_at)
    if time_since_last_message == -1 or time_since_last_message > 300:
        issues.append("no_recent_messages")

    return status, issues


async def _change_visibility_loop(message: message_queue.Message):
    """Change the message visibility while it's been processed"""
    try:
        while app.running():
            await message_queue.change_visibility(message)
            await app.sleep(configs.queue_visibility_time)
    except asyncio.CancelledError:
        return


class Executor:
    task: asyncio.Task
    _logger: logging.Logger

    _handlers = {
        "event": reaction_handler.run,
        "process_monitor": monitor_handler.run,
        "request": request_handler.run,
    }
    _current_message_type: str

    def __init__(self, number: int):
        self._logger = logging.getLogger(f"executor_{number}")

    def init(self):
        """Create the internal loop task"""
        self.task = asyncio.create_task(self.run())

    async def get_message(self) -> message_queue.Message | None:
        """Try to get a message from the queue"""
        global last_message_at

        message = await message_queue.get_message()
        if message is not None:
            last_message_at = now()

        return message

    def get_message_handler(
        self, message: message_queue.Message
    ) -> Callable[[dict[Any, Any]], Coroutine[Any, Any, Any]] | None:
        """Get the correct handler for the message"""
        handler = self._handlers.get(message.content["type"])

        if not handler:
            self._logger.warning(
                f"Didn't find a handler for message '{json.dumps(message.content)}'"
            )

        return handler

    async def process_message(
        self,
        handler: Callable[[dict[Any, Any]], Coroutine[Any, Any, Any]],
        message: message_queue.Message
    ):
        """Process the message with the provided handler, protecting from possible exceptions.
        During the message processing, another task will be spawned to change it's visibility in
        the queue, preventing other messages from processing it too"""
        self._logger.info(f"Got message '{json.dumps(message.content)}'")
        message_type = message.content["type"]

        prometheus_message_processing_count.labels(message_type=message_type).inc()

        # Create a looping task that will keep the message not visible while it's been
        # handled
        change_visibility_task = asyncio.create_task(_change_visibility_loop(message))

        # Protect execution from exceptions
        try:
            # Handle the message accordingly
            await handler(message.content)
            # Only delete the message from the queue when it's been successfully handled
            await message_queue.delete_message(message)
        except BaseSentinelaException as e:
            _logger.error(str(e))
        except Exception:
            prometheus_message_error_count.labels(message_type=message_type).inc()

            self._logger.error(traceback.format_exc().strip())
            self._logger.error(f"Message: '{json.dumps(message.content)}'")
            self._logger.info("Exception caught successfully, going on")
        finally:
            prometheus_message_processing_count.labels(
                message_type=message_type
            ).dec()

            # Stop the message change visibility loop
            change_visibility_task.cancel()
            await change_visibility_task

    async def process(self):
        """Get a message and process it"""
        # Wait for the monitors to be ready
        await registry.wait_monitors_ready()

        message = await self.get_message()
        if message is None:
            await app.sleep(configs.executor_sleep)
            return

        handler = self.get_message_handler(message)
        if handler is None:
            return

        prometheus_message_count.labels(message_type=message.content["type"]).inc()

        await self.process_message(handler, message)

    async def run(self):
        """Run the executor process continuously, until the application finishes"""
        self._logger.info("Executor running")

        while app.running():
            with catch_exceptions():
                await self.process()

        self._logger.info("Finishing")


async def run():
    global executors
    global running

    running = True

    _logger.info("Executor running")

    # Executors initialization
    for i in range(configs.executor_concurrency):
        executor = Executor(i)
        executor.init()
        executors.append(executor)

    while app.running():
        executors = [executor for executor in executors if not executor.task.done()]
        await app.sleep(60)

    # Wait for all executors to finish
    _logger.info("Finishing")
    await asyncio.gather(*[executor.task for executor in executors])

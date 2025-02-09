import asyncio
import json
import logging
import traceback
from typing import Any, Callable, Coroutine

import prometheus_client

import message_queue as message_queue
import registry as registry
import utils.app as app
from base_exception import BaseSentinelaException
from utils.exception_handling import catch_exceptions

from . import event_handler, monitor_handler, request_handler

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


async def _change_visibility_loop(message: message_queue.Message) -> None:
    """Change the message visibility while it's been processed"""
    try:
        while app.running():
            await message_queue.change_visibility(message)
            await app.sleep(message_queue.get_queue_wait_message_time())
    except asyncio.CancelledError:
        return


class Runner:
    _logger: logging.Logger
    message: message_queue.Message

    _handlers = {
        "event": event_handler.run,
        "process_monitor": monitor_handler.run,
        "request": request_handler.run,
    }

    def __init__(self, runner_id: int, message: message_queue.Message) -> None:
        self._logger = logging.getLogger(f"runner_{runner_id}")
        self.message = message

    def get_message_handler(self) -> Callable[[dict[Any, Any]], Coroutine[Any, Any, Any]] | None:
        """Get the correct handler for the message"""
        handler = self._handlers.get(self.message.content["type"])

        if not handler:
            self._logger.warning(
                f"Didn't find a handler for message '{json.dumps(self.message.content)}'"
            )

        return handler

    async def process_message(
        self,
        handler: Callable[[dict[Any, Any]], Coroutine[Any, Any, Any]],
    ) -> None:
        """Process the message with the provided handler, protecting from possible exceptions.
        During the message processing, another task will be spawned to change it's visibility in
        the queue, preventing other messages from processing it too"""
        self._logger.info(f"Got message '{json.dumps(self.message.content)}'")
        message_type = self.message.content["type"]

        prometheus_message_processing_count.labels(message_type=message_type).inc()

        # Create a looping task that will keep the message not visible while it's been
        # handled
        change_visibility_task = asyncio.create_task(_change_visibility_loop(self.message))

        # Protect execution from exceptions
        try:
            # Handle the message accordingly
            await handler(self.message.content)
            # Only delete the message from the queue when it's been successfully handled
            await message_queue.delete_message(self.message)
        except BaseSentinelaException as e:
            self._logger.error(str(e))
        except Exception:
            prometheus_message_error_count.labels(message_type=message_type).inc()

            self._logger.error(traceback.format_exc().strip())
            self._logger.error(f"Message: '{json.dumps(self.message.content)}'")
            self._logger.info("Exception caught successfully, going on")
        finally:
            prometheus_message_processing_count.labels(message_type=message_type).dec()

            # Stop the message change visibility loop
            change_visibility_task.cancel()
            await change_visibility_task

    async def process(self, semaphore: asyncio.Semaphore) -> None:
        """Get a message and process it"""
        async with semaphore:
            with catch_exceptions(self._logger):
                # Wait for the monitors to be ready
                await registry.wait_monitors_ready()

                handler = self.get_message_handler()
                if handler is None:
                    return

                prometheus_message_count.labels(message_type=self.message.content["type"]).inc()

                await self.process_message(handler)

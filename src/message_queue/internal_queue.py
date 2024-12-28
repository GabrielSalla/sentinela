import asyncio
import json
import logging
from typing import Any

from configs import configs

_logger = logging.getLogger("internal_queue")
_queue: asyncio.Queue


class Message:
    message: dict[str, Any]

    def __init__(self, message: str):
        self.message = json.loads(message)

    @property
    def content(self) -> dict[str, Any]:
        return self.message


async def init():
    """Setup the internal queue"""
    global _queue

    _logger.info("Internal queue setup")
    _queue = asyncio.Queue()


async def send_message(type: str, payload: dict[str, Any]):
    """Send a message to the queue"""
    global _queue
    await _queue.put(
        json.dumps(
            {
                "type": type,
                "payload": payload,
            }
        )
    )


async def get_message() -> Message | None:
    """Get a message from the queue"""
    global _queue
    try:
        return Message(await asyncio.wait_for(_queue.get(), configs.queue_wait_message_time))
    except asyncio.TimeoutError:
        return None


async def change_visibility(message: Message):
    """Not implemented in internal queue"""
    pass


async def delete_message(message: Message):
    """Not implemented in internal queue"""
    pass

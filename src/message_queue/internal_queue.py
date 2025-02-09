import asyncio
import json
import logging
from typing import Any, Literal

from pydantic.dataclasses import dataclass

from message_queue.protocols import Message

_logger = logging.getLogger("internal_queue")


@dataclass
class InternalQueueConfig:
    type: Literal["internal"]
    queue_wait_message_time: float = 2


class InternalMessage:
    id: str = ""
    message: dict[str, Any]

    def __init__(self, message: str) -> None:
        self.message = json.loads(message)

    @property
    def content(self) -> dict[str, Any]:
        return self.message


class InternalQueue:
    _config: InternalQueueConfig
    _queue: asyncio.Queue[str]

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = InternalQueueConfig(**config)

    @property
    def queue_wait_message_time(self) -> float:
        return self._config.queue_wait_message_time

    async def init(self) -> None:
        """Setup the internal queue"""
        _logger.info("Internal queue setup")
        self._queue = asyncio.Queue()

    async def send_message(self, type: str, payload: dict[str, Any]) -> None:
        """Send a message to the queue"""
        await self._queue.put(
            json.dumps(
                {
                    "type": type,
                    "payload": payload,
                }
            )
        )

    async def get_message(self) -> Message | None:
        """Get a message from the queue"""
        try:
            return InternalMessage(
                await asyncio.wait_for(self._queue.get(), self._config.queue_wait_message_time)
            )
        except asyncio.TimeoutError:
            return None

    async def change_visibility(self, message: Message) -> None:
        """Not implemented in internal queue"""
        pass

    async def delete_message(self, message: Message) -> None:
        """Not implemented in internal queue"""
        pass

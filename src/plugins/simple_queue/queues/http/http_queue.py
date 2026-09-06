import logging
from typing import Any, Literal, cast

from aiohttp import ClientSession
from pydantic.dataclasses import dataclass

from message_queue.protocols import Message

_logger = logging.getLogger("simple_queue")
WAIT_MESSAGE_TIME = 2


@dataclass
class SimpleQueueConfig:
    type: Literal["plugin.simple_queue.queues.http"]
    url: str


class SimpleQueueMessage:
    def __init__(self, message: dict[str, Any]) -> None:
        self.id = message["id"]
        self._content = message["content"]

    @property
    def content(self) -> dict[str, Any]:
        return cast(dict[str, Any], self._content)


class Queue:
    _config: SimpleQueueConfig

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = SimpleQueueConfig(**config)

    @property
    def queue_wait_message_time(self) -> float:
        return WAIT_MESSAGE_TIME

    @property
    def _url(self) -> str:
        return self._config.url.rstrip("/")

    async def init(self) -> None:
        """Initialize the Simple Queue client."""
        _logger.info("Simple Queue setup")

    async def send_message(self, type: str, payload: dict[str, Any]) -> None:
        """Send a message to Simple Queue."""
        async with ClientSession() as session:
            async with session.post(
                f"{self._url}/messages",
                json={"type": type, "payload": payload},
            ) as response:
                response.raise_for_status()

    async def get_message(self) -> Message | None:
        """Get a message from Simple Queue."""
        async with ClientSession() as session:
            async with session.get(f"{self._url}/messages") as response:
                if response.status == 204:
                    return None
                response.raise_for_status()
                return SimpleQueueMessage(await response.json())

    async def change_visibility(self, message: Message) -> None:
        """Extend a message's visibility lease."""
        async with ClientSession() as session:
            async with session.post(f"{self._url}/messages/{message.id}/visibility") as response:
                response.raise_for_status()

    async def delete_message(self, message: Message) -> None:
        """Delete a message from Simple Queue."""
        async with ClientSession() as session:
            async with session.delete(f"{self._url}/messages/{message.id}") as response:
                response.raise_for_status()

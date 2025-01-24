from typing import Any

from configs import configs
from message_queue.internal_queue import InternalQueue
from message_queue.protocols import Message, Queue
from message_queue.sqs_queue import SQSQueue

queue: Queue


async def init() -> None:
    """Initialize the queue"""
    global queue

    if configs.application_queue.type == "internal":
        queue = InternalQueue()
    elif configs.application_queue.type == "sqs":
        queue = SQSQueue(configs.application_queue)
    else:
        raise ValueError(  # pragma: no cover
            f"Invalid queue type '{configs.application_queue.type}'"
        )

    await queue.init()


async def send_message(type: str, payload: dict[str, Any]) -> None:
    """Send a message to the queue"""
    global queue
    return await queue.send_message(type, payload)


async def get_message() -> Message | None:
    """Get a message from the queue"""
    global queue
    return await queue.get_message()


async def change_visibility(message: Message) -> None:
    """Change the visibility time for a message in the queue"""
    global queue
    return await queue.change_visibility(message)


async def delete_message(message: Message) -> None:
    """Delete a message from the queue"""
    global queue
    return await queue.delete_message(message)


__all__ = [
    "change_visibility",
    "delete_message",
    "get_message",
    "init",
    "Message",
    "send_message",
]

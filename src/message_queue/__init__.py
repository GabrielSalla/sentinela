from typing import Any

from configs import configs

from .internal_queue import InternalQueue
from .protocols import Message, Queue
from .queue_select import get_plugin_queue

queue: Queue


async def init() -> None:
    """Initialize the queue, identifying if it's internal or a queue from an installed plugin"""
    global queue

    queue_type = configs.application_queue["type"]

    if queue_type == "internal":
        queue = InternalQueue(config=configs.application_queue)
    elif queue_type.startswith("plugin."):
        queue_class = get_plugin_queue(queue_type)
        queue = queue_class(config=configs.application_queue)
    else:
        raise ValueError(f"Invalid queue type '{queue_type}'")

    await queue.init()


def get_queue_wait_message_time() -> float:
    """Get the time to wait for a message in the queue"""
    return queue.queue_wait_message_time


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

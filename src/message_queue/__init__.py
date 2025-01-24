from typing import Any

from configs import configs

queue_type = configs.application_queue["type"]

match queue_type:
    case "internal":
        import message_queue.internal_queue as queue
    case "sqs":  # pragma: no cover
        # As the 'queue' variable is being redefined, ignore the typing and linter errors
        import message_queue.sqs_queue as queue  # type: ignore[no-redef] # noqa: F811
    case _:  # pragma: no cover
        raise ValueError(f"Invalid queue type '{queue_type}'")

Message = queue.Message


async def init() -> None:
    """Initialize the queue"""
    return await queue.init()


async def send_message(type: str, payload: dict[str, Any]) -> None:
    """Send a message to the queue"""
    return await queue.send_message(type, payload)


async def get_message() -> queue.Message | None:
    """Get a message from the queue"""
    return await queue.get_message()


async def change_visibility(message: queue.Message) -> None:
    """Change the visibility time for a message in the queue"""
    return await queue.change_visibility(message)


async def delete_message(message: queue.Message) -> None:
    """Delete a message from the queue"""
    return await queue.delete_message(message)


__all__ = [
    "change_visibility",
    "delete_message",
    "get_message",
    "init",
    "Message",
    "send_message",
]

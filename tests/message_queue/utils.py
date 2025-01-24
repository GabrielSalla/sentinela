import message_queue


def get_queue_items() -> list[str]:
    """Return all items in the internal message queue. Ignoring the 'attr-defined' error because
    the Protocol doesn't have the attribute '_queue', but the 'InternalQueue' class does"""
    queue_items = []
    while not message_queue.queue._queue.empty():  # type: ignore[attr-defined]
        queue_items.append(message_queue.queue._queue.get_nowait())  # type: ignore[attr-defined]
    return queue_items

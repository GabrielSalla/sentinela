import logging
from typing import cast

import plugins
from message_queue.protocols import Queue

_logger = logging.getLogger("queue_select")


def get_plugin_queue(queue_type: str) -> type[Queue]:
    _, plugin_name, queue_type = queue_type.split(".")

    plugin = plugins.loaded_plugins.get(plugin_name)
    if plugin is None:
        raise ValueError(f"Plugin '{plugin_name}' not loaded")

    plugin_queue = getattr(plugin, "queue", None)
    if plugin_queue is None:
        raise ValueError(f"Plugin '{plugin_name}' has no queues")

    queue = getattr(plugin_queue, queue_type, None)
    if queue is None:
        raise ValueError(f"Plugin '{plugin_name}' has no queue '{queue_type}'")

    try:
        return cast(type[Queue], queue.Queue)
    except AttributeError:
        raise ValueError(f"Plugin '{plugin_name}' queue '{queue_type}' has no 'Queue' class")

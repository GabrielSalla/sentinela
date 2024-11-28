import asyncio
import json
import logging
import traceback
from functools import partial
from typing import Any

import prometheus_client

import src.registry as registry
from src.base_exception import BaseSentinelaException
from src.configs import configs
from src.models import Monitor

_logger = logging.getLogger("reaction_handler")

prometheus_reaction_error_count = prometheus_client.Counter(
    "reaction_execution_error",
    "Error count for reactions",
    ["monitor_id", "monitor_name", "event_name"],
)
prometheus_reaction_timeout_count = prometheus_client.Counter(
    "reaction_execution_timeout",
    "Timeout count for reactions",
    ["monitor_id", "monitor_name", "event_name"],
)
prometheus_reaction_execution_time = prometheus_client.Summary(
    "reaction_execution_seconds",
    "Time to run the reaction",
    ["monitor_id", "monitor_name", "event_name"],
)


async def run(message: dict[Any, Any]):
    """Process a message with type 'event' using the monitor's defined list of reactions for the
    event. The execution timeout is for each function individually"""
    message_payload = message["payload"]
    monitor_id = message_payload["event_source_monitor_id"]
    event_name = message_payload["event_name"]

    monitor = await Monitor.get_by_id(monitor_id)
    if monitor is None:
        _logger.error(f"Monitor {monitor_id} not found. Skipping message")
        return

    await registry.wait_monitor_loaded(monitor_id)

    prometheus_labels = {
        "monitor_id": monitor.id,
        "monitor_name": monitor.name,
        "event_name": event_name,
    }

    reactions = monitor.code.reaction_options

    for reaction in reactions[event_name]:
        # Get the reaction function name
        try:
            if isinstance(reaction, partial):
                reaction_name = reaction.func.__name__
            else:
                reaction_name = reaction.__name__
        except AttributeError:
            reaction_name = str(reaction)

        reaction_execution_time = prometheus_reaction_execution_time.labels(**prometheus_labels)
        try:
            with reaction_execution_time.time():
                await asyncio.wait_for(reaction(message_payload), configs.executor_reaction_timeout)
        except asyncio.TimeoutError:
            prometheus_reaction_timeout_count.labels(**prometheus_labels).inc()
            _logger.error(
                f"Timed out executing reaction '{reaction_name}' with payload "
                f"'{json.dumps(message_payload)}'"
            )
        except BaseSentinelaException as e:
            raise e
        except Exception:
            prometheus_reaction_error_count.labels(**prometheus_labels).inc()
            _logger.error(
                f"Error executing reaction '{reaction_name}' with payload "
                f"'{json.dumps(message_payload)}'"
            )
            _logger.error(traceback.format_exc().strip())

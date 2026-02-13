import logging
import time
from collections import deque
from itertools import pairwise

import prometheus_client

import utils.app as app
from configs import configs

_logger = logging.getLogger("heartbeat")

prometheus_heartbeat_average_time = prometheus_client.Gauge(
    "heartbeat_average_time", "Average time between heartbeats in seconds"
)


def _is_heartbeat_delayed(timestamps: deque[float], threshold: float) -> bool:
    """Determine if the heartbeat is delayed based on the average latency between timestamps"""
    if len(timestamps) < 2:
        return False

    latencies = [b - a for a, b in pairwise(timestamps)]
    average_latency = sum(latencies) / len(latencies)
    prometheus_heartbeat_average_time.set(average_latency)
    return average_latency > threshold


async def run() -> None:
    """Create a heartbeat for the application to detect when some tasks are not yielding control
    back to the event loop. If the heartbeat is delayed, a warning message is logged."""
    timestamps = deque[float](maxlen=10)
    last_warning_timestamp = 0.0

    while app.running():
        timestamp = time.time()
        timestamps.append(timestamp)
        heartbeat_delayed = _is_heartbeat_delayed(timestamps, configs.heartbeat_time * 1.05)

        # Prevent warning messages from being sent too frequently
        can_warn = timestamp - last_warning_timestamp > 10
        if can_warn and heartbeat_delayed:
            _logger.warning(
                "High average heartbeat interval. "
                "Blocking operations are preventing tasks from executing"
            )
            last_warning_timestamp = timestamp

        await app.sleep(configs.heartbeat_time)

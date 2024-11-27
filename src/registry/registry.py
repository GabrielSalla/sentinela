"""
This module is intended as a middleware between the Monitors Loader module and other modules.
As many things have to access the monitor's modules, like Monitors, Alerts and Issues, and the
Monitors Loader module imports the Monitor model, they can't use the Monitors Loader module
directly.
Another requirement is that getting the monit's modules should be done using a synchronous fast
process, so fetching it from the database would be unfeasible.
As a solution, this module is used to store the monitor's modules, where the Monitors Loader will
register them, and other modules can access.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, TypedDict

import prometheus_client

from .exceptions import MonitorNotRegisteredError, MonitorsLoadError

if TYPE_CHECKING:
    from src.components.monitors_loader.monitor_module_type import MonitorModule

MONITORS_READY_TIMEOUT = 5

_logger = logging.getLogger("registry")


class MonitorInfo(TypedDict):
    name: str
    module: MonitorModule


_monitors: dict[int, MonitorInfo] = {}
monitors_ready: asyncio.Event = asyncio.Event()
monitors_pending: asyncio.Event = asyncio.Event()

prometheus_monitors_ready_timeout_count = prometheus_client.Counter(
    "monitors_ready_timeout_count",
    "Count of times the application timed out waiting for monitors to be ready",
)
prometheus_monitor_not_registered_count = prometheus_client.Counter(
    "monitor_not_registered_count",
    "Count of times a monitor is not registered after a load attempt",
)


async def wait_monitors_ready():
    """Wait for the monitors to be ready, with a timeout"""
    try:
        await asyncio.wait_for(monitors_ready.wait(), timeout=MONITORS_READY_TIMEOUT)
    except asyncio.TimeoutError:
        prometheus_monitors_ready_timeout_count.inc()
        raise MonitorsLoadError("Waiting for monitors to be ready timed out")


def is_monitor_registered(monitor_id: int) -> bool:
    """Check if a monitor is registered"""
    return monitor_id in _monitors


async def wait_monitor_loaded(monitor_id: int):
    """Wait for a monitor to be loaded and raise an 'MonitorNotRegisteredError' if it fails to
    load"""
    if is_monitor_registered(monitor_id):
        return

    # Signal for the monitors to be reloaded
    monitors_ready.clear()
    monitors_pending.set()
    await wait_monitors_ready()

    if not is_monitor_registered(monitor_id):
        prometheus_monitor_not_registered_count.inc()
        raise MonitorNotRegisteredError(f"Monitor '{monitor_id}' not registered")


def get_monitors() -> list[MonitorInfo]:
    """Get all the monitors"""
    return list(_monitors.values())


def get_monitor_module(monitor_id: int) -> MonitorModule:
    """Get the monitor module"""
    return _monitors[monitor_id]["module"]


def add_monitor(monitor_id: int, monitor_name: str, monitor_module: MonitorModule):
    """Add a monitor to the registry"""
    _monitors[monitor_id] = {"name": monitor_name, "module": monitor_module}


def init():
    monitors_ready.clear()
    monitors_pending.set()

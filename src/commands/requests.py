import random
import string
import time
from typing import Any

import components.monitors_loader as monitors_loader
import message_queue as message_queue
from models import Monitor

from .validations import validate_alert_request, validate_issue_request, validate_monitor_request


async def monitor_code_validate(monitor_code: str, log_error: bool = True) -> None:
    """Validate a monitor code without registering it"""
    timestamp_string = str(int(time.time()))
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    monitors_loader.check_monitor(
        f"monitor_{timestamp_string}_{random_string}",
        monitor_code,
        log_error=log_error,
    )


async def monitor_register(
    monitor_name: str, monitor_code: str, additional_files: dict[str, str], log_error: bool = True
) -> Monitor:
    """Register a monitor"""
    return await monitors_loader.register_monitor(
        monitor_name,
        monitor_code,
        additional_files=additional_files,
        internal=False,
        log_error=log_error,
    )


async def monitor_disable(monitor_name: str, context: dict[str, Any] | None = None) -> int:
    """Validate and queue a 'monitor_disable' request"""
    monitor = await validate_monitor_request(monitor_name)
    params: dict[str, Any] = {"target_id": monitor.id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_disable",
            "params": params,
        },
    )
    return monitor.id


async def monitor_enable(monitor_name: str, context: dict[str, Any] | None = None) -> int:
    """Validate and queue a 'monitor_enable' request"""
    monitor = await validate_monitor_request(monitor_name)
    params: dict[str, Any] = {"target_id": monitor.id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_enable",
            "params": params,
        },
    )
    return monitor.id


async def monitor_refresh(monitor_name: str, tasks: list[str]) -> None:
    """Validate and queue a 'monitor_refresh' request"""
    monitor = await validate_monitor_request(monitor_name)
    if monitor.queued or monitor.running:
        raise ValueError(f"Monitor {monitor_name!r} already running or queued")
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_refresh",
            "params": {"target_id": monitor.id, "tasks": tasks},
        },
    )


async def alert_acknowledge(alert_id: int, context: dict[str, Any] | None = None) -> None:
    """Validate and queue an 'alert_acknowledge' request"""
    await validate_alert_request(alert_id)
    params: dict[str, Any] = {"target_id": alert_id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_acknowledge",
            "params": params,
        },
    )


async def alert_lock(alert_id: int, context: dict[str, Any] | None = None) -> None:
    """Validate and queue an 'alert_lock' request"""
    await validate_alert_request(alert_id)
    params: dict[str, Any] = {"target_id": alert_id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_lock",
            "params": params,
        },
    )


async def alert_solve(alert_id: int, context: dict[str, Any] | None = None) -> None:
    """Validate and queue an 'alert_solve' request"""
    await validate_alert_request(alert_id)
    params: dict[str, Any] = {"target_id": alert_id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_solve",
            "params": params,
        },
    )


async def issue_drop(issue_id: int, context: dict[str, Any] | None = None) -> None:
    """Validate and queue an 'issue_drop' request"""
    await validate_issue_request(issue_id)
    params: dict[str, Any] = {"target_id": issue_id}
    if context is not None:
        params["context"] = context
    await message_queue.send_message(
        type="request",
        payload={
            "action": "issue_drop",
            "params": params,
        },
    )

import random
import string
import time

import components.monitors_loader as monitors_loader
import message_queue as message_queue
from models import Monitor

from .validations import validate_alert_request, validate_issue_request, validate_monitor_request


async def monitor_code_validate(monitor_code: str) -> None:
    """Validate a monitor code without registering it"""
    timestamp_string = str(int(time.time()))
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    monitors_loader.check_monitor(f"monitor_{timestamp_string}_{random_string}", monitor_code)


async def monitor_register(
    monitor_name: str, monitor_code: str, additional_files: dict[str, str], log_error: bool = True
) -> Monitor:
    """Register a monitor"""
    return await monitors_loader.register_monitor(
        monitor_name, monitor_code, additional_files=additional_files, log_error=log_error
    )


async def monitor_disable(monitor_name: str) -> int:
    """Validate and queue a 'monitor_disable' request"""
    monitor = await validate_monitor_request(monitor_name)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_disable",
            "params": {"target_id": monitor.id},
        },
    )
    return monitor.id


async def monitor_enable(monitor_name: str) -> int:
    """Validate and queue a 'monitor_enable' request"""
    monitor = await validate_monitor_request(monitor_name)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_enable",
            "params": {"target_id": monitor.id},
        },
    )
    return monitor.id


async def monitor_refresh(monitor_name: str, tasks: list[str]) -> None:
    """Validate and queue a 'monitor_refresh' request"""
    monitor = await validate_monitor_request(monitor_name)
    if monitor.queued or monitor.running:
        raise ValueError(f"Monitor '{monitor_name}' already running or queued")
    await message_queue.send_message(
        type="request",
        payload={
            "action": "monitor_refresh",
            "params": {"target_id": monitor.id, "tasks": tasks},
        },
    )


async def alert_acknowledge(alert_id: int) -> None:
    """Validate and queue an 'alert_acknowledge' request"""
    await validate_alert_request(alert_id)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_acknowledge",
            "params": {"target_id": alert_id},
        },
    )


async def alert_lock(alert_id: int) -> None:
    """Validate and queue an 'alert_lock' request"""
    await validate_alert_request(alert_id)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_lock",
            "params": {"target_id": alert_id},
        },
    )


async def alert_solve(alert_id: int) -> None:
    """Validate and queue an 'alert_solve' request"""
    await validate_alert_request(alert_id)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_solve",
            "params": {"target_id": alert_id},
        },
    )


async def issue_drop(issue_id: int) -> None:
    """Validate and queue an 'issue_drop' request"""
    await validate_issue_request(issue_id)
    await message_queue.send_message(
        type="request",
        payload={
            "action": "issue_drop",
            "params": {"target_id": issue_id},
        },
    )

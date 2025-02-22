import random
import string
import time

import components.monitors_loader as monitors_loader
import message_queue as message_queue
from models import Monitor


async def monitor_code_validate(monitor_code: str) -> None:
    """Validate a monitor code without registering it"""
    timestamp_string = str(int(time.time()))
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(8))
    monitors_loader.check_monitor(f"monitor_{timestamp_string}_{random_string}", monitor_code)


async def monitor_register(
    monitor_name: str, monitor_code: str, additional_files: dict[str, str]
) -> Monitor:
    """Register a monitor"""
    return await monitors_loader.register_monitor(
        monitor_name, monitor_code, additional_files=additional_files
    )


async def disable_monitor(monitor_name: str) -> str:
    """Disable a monitor"""
    monitor = await Monitor.get(Monitor.name == monitor_name)

    if monitor is None:
        raise ValueError(f"Monitor '{monitor_name}' not found")

    await monitor.set_enabled(False)
    return f"{monitor} disabled"


async def enable_monitor(monitor_name: str) -> str:
    """Enable a monitor"""
    monitor = await Monitor.get(Monitor.name == monitor_name)

    if monitor is None:
        raise ValueError(f"Monitor '{monitor_name}' not found")

    await monitor.set_enabled(True)
    return f"{monitor} enabled"


async def alert_acknowledge(alert_id: int) -> None:
    """Queue an 'alert_acknowledge' request"""
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_acknowledge",
            "params": {"target_id": alert_id},
        },
    )


async def alert_lock(alert_id: int) -> None:
    """Queue an 'alert_lock' request"""
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_lock",
            "params": {"target_id": alert_id},
        },
    )


async def alert_solve(alert_id: int) -> None:
    """Queue an 'alert_solve' request"""
    await message_queue.send_message(
        type="request",
        payload={
            "action": "alert_solve",
            "params": {"target_id": alert_id},
        },
    )


async def issue_drop(issue_id: int) -> None:
    """Queue an 'issue_drop' request"""
    await message_queue.send_message(
        type="request",
        payload={
            "action": "issue_drop",
            "params": {"target_id": issue_id},
        },
    )

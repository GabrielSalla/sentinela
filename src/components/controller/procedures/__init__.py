from typing import Callable, Coroutine

from . import monitors_stuck, notifications_alert_solved

procedures: dict[str, Callable[..., Coroutine[None, None, None]]] = {
    "monitors_stuck": monitors_stuck.monitors_stuck,
    "notifications_alert_solved": notifications_alert_solved.notifications_alert_solved,
}

__all__ = ["procedures"]

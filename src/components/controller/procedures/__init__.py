from typing import Callable, Coroutine

from . import monitors_stuck

procedures: dict[str, Callable[..., Coroutine[None, None, None]]] = {
    "monitors_stuck": monitors_stuck.monitors_stuck,
}

__all__ = ["procedures"]

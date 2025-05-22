from types import ModuleType
from typing import cast

from models import Variable
from utils.stack import get_caller

"""The functions 'set_variable' and 'get_variable' must be called from inside a monitor to be able
to identify the monitor ID. If called outside a monitor, they will raise an error."""


def _get_monitor_id(monitor_module: ModuleType) -> int:
    """Get the monitor ID from the monitor module"""
    monitor_id = getattr(monitor_module, "SENTINELA_MONITOR_ID", None)
    if monitor_id is None:
        raise ValueError("Function called outside a monitor or the monitor was not loaded properly")

    return cast(int, monitor_id)


async def set_variable(name: str, value: str | None) -> None:
    """Set a variable for the monitor. Must be called from inside a monitor or an error will be
    raised."""
    monitor_module, _ = get_caller()
    monitor_id = _get_monitor_id(monitor_module)

    variable = await Variable.get_or_create(monitor_id=monitor_id, name=name)
    await variable.set(value)


async def get_variable(name: str) -> str | None:
    """Get a variable for the monitor, or None if it does not exist. Must be called from inside a
    monitor or an error will be raised."""
    monitor_module, _ = get_caller()
    monitor_id = _get_monitor_id(monitor_module)

    variable = await Variable.get(Variable.monitor_id == monitor_id, Variable.name == name)
    if variable is None:
        return None

    return variable.value

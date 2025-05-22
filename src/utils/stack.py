import inspect
from types import ModuleType


def get_caller(previous: int = 0) -> tuple[ModuleType, str]:
    """Get the module of the caller function"""
    stack_position = 2 + previous

    stack = inspect.stack()

    if len(stack) < stack_position:
        raise IndexError(f"Could not access position {stack_position} in the stack")

    caller_frame = stack[stack_position][0]
    module = inspect.getmodule(caller_frame)
    if module is None:
        raise ValueError("Could not determine caller module")

    return module, caller_frame.f_code.co_name

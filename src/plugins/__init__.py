from types import ModuleType

from . import services
from .plugins_loader import load_plugins as __load_plugins

loaded_plugins: dict[str, ModuleType]


def load_plugins() -> dict[str, ModuleType]:
    """Load the plugins and return it as a dictionary"""
    global loaded_plugins
    loaded_plugins = __load_plugins()
    return loaded_plugins


__all__ = [
    "load_plugins",
    "services",
]

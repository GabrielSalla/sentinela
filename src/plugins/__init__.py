from types import ModuleType
from .plugins_loader import load_plugins as __load_plugins

loaded_plugins: dict[str, ModuleType]


def load_plugins():
    global loaded_plugins
    loaded_plugins = __load_plugins()
    return loaded_plugins

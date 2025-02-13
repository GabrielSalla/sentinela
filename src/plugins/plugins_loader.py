import importlib
import logging
import os
import traceback
from pathlib import Path
from types import ModuleType

from configs import configs

_logger = logging.getLogger("plugins_loader")


def load_plugins(path: str | None = None) -> dict[str, ModuleType]:
    """Load all plugins from the plugins directory"""
    if path is None:
        plugins_directory = Path(__file__).parent.relative_to(Path.cwd())
    else:
        plugins_directory = Path(path)

    # Get all plugins names from the plugins directory
    plugins_names = []
    for item in os.listdir(plugins_directory):
        if item == "__pycache__":
            continue

        if os.path.isdir(plugins_directory / item):
            plugins_names.append(item)

    # Load all enabled plugins
    plugins_relative_path = plugins_directory.relative_to("src")
    plugins_import_path = plugins_relative_path.as_posix().replace("/", ".")
    plugins = {}
    for plugin_name in plugins_names:
        # Skip not enabled plugins
        if plugin_name not in configs.plugins:
            continue

        try:
            plugin = importlib.import_module(f"{plugins_import_path}.{plugin_name}")
            plugins[plugin_name] = plugin
        except Exception:
            _logger.error(f"Error loading plugin '{plugin_name}'")
            _logger.error(traceback.format_exc().strip())

    return plugins

from typing import Any

import plugins


def get_plugin_attribute(attribute_path: str) -> Any:
    """Retrieves a plugin attribute based on the provided attribute path."""
    _, plugin_name, *parts = attribute_path.split(".")
    if len(parts) < 2:
        raise ValueError("Attribute path must specify a plugin and at least two attributes")

    plugin = plugins.loaded_plugins.get(plugin_name)
    if plugin is None:
        raise ValueError(f"Plugin '{plugin_name}' not loaded")

    target_path_parts = []
    target: Any = plugin

    for part in parts:
        target_path_parts.append(part)
        target = getattr(target, part, None)

        if target is None:
            target_path = ".".join(target_path_parts)
            raise ValueError(f"Plugin '{plugin_name}' has no attribute '{target_path}'")

    return target

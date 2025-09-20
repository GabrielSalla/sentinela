"""Tool to get the list of plugins from the environment variable to install the required
dependencies"""

import os
import sys

import yaml


def _make_plugin_name(environment: str | None, plugin: str) -> str:
    plugin_name = f"plugin-{plugin.strip()}"
    if environment:
        return f"{plugin_name}-{environment}"
    return plugin_name


environment = sys.argv[1] if len(sys.argv) > 1 else None

with open(os.environ.get("CONFIGS_FILE", "configs.yaml"), "r") as file:
    configs = yaml.load(file.read(), Loader=yaml.FullLoader)

if configs["plugins"]:
    plugins_list = [_make_plugin_name(environment, plugin) for plugin in configs["plugins"]]
    print(",".join(plugins_list))

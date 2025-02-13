"""Tool to get the list of plugins from the environment variable to install the required
dependencies"""

import os

import yaml

with open(os.environ.get("CONFIGS_FILE", "configs.yaml"), "r") as file:
    configs = yaml.load(file.read(), Loader=yaml.FullLoader)

if configs["plugins"]:
    plugins_list = [f"plugin-{plugin.strip()}" for plugin in configs["plugins"]]
    print(",".join(plugins_list))

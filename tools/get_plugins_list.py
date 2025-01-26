"""Tool to get the list of plugins from the environment variable to install the required
dependencies"""

import os

plugins = os.environ.get("SENTINELA_PLUGINS")

if not plugins:
    print("main")
else:
    plugins_list = [f"plugin-{plugin.strip()}" for plugin in plugins.split(",")]
    print("main," + ",".join(plugins_list))

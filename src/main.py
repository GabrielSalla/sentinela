# Still missing tests for main.py, so it's been ignored in the .coveragerc file

import asyncio
import logging
import sys
import traceback
from typing import Coroutine

import uvloop

import components.controller as controller
import components.executor as executor
import components.http_server as http_server
import components.monitors_loader as monitors_loader
import databases as databases
import internal_database as internal_database
import message_queue as message_queue
import plugins as plugins
import registry as registry
import utils.app as app
import utils.log as log

_logger = logging.getLogger("main")


async def protected_task(task: Coroutine[None, None, None]) -> None:
    try:
        await task
    except Exception:
        _logger.error(f"Exception with task '{task}'")
        _logger.error(traceback.format_exc().strip())


async def init_plugins_services(controller_enabled: bool, executor_enabled: bool) -> None:
    """Initialize the plugins services"""
    for plugin_name, plugin in plugins.loaded_plugins.items():
        _logger.info(f"Loading plugin '{plugin_name}'")

        plugin_services = getattr(plugin, "services", None)
        if plugin_services is None:
            _logger.info(f"Plugin '{plugin_name}' has no services")
            continue

        for service_name in plugin_services.__all__:
            service = getattr(plugin_services, service_name)
            if hasattr(service, "init"):
                await service.init(controller_enabled, executor_enabled)
                _logger.info(f"Service '{plugin_name}.{service_name}' initialized")
            else:
                _logger.warning(f"Service '{plugin_name}.{service_name}' has no 'init' function")


async def init(controller_enabled: bool, executor_enabled: bool) -> None:
    """Initialize the application dependencies. Some of the components will behave differently if
    they start with or without the controller."""
    # Log setup must be the first one
    log.setup()
    app.setup()
    registry.init()
    await databases.init()
    # Depends on internal database migrated
    await monitors_loader.init(controller_enabled)
    await http_server.init(controller_enabled)

    plugins.load_plugins()
    await init_plugins_services(controller_enabled, executor_enabled)

    # As the queue might be provided by a plugin, only start the queue after the plugins have been
    # loaded
    await message_queue.init()


async def stop_plugins_services() -> None:
    """Stop the plugins services"""
    for plugin_name, plugin in plugins.loaded_plugins.items():
        _logger.info(f"Stopping plugin '{plugin_name}'")

        plugin_services = getattr(plugin, "services", None)
        if plugin_services is None:
            continue

        for service_name in plugin_services.__all__:
            service = getattr(plugin_services, service_name)
            if hasattr(service, "stop"):
                await protected_task(service.stop())


async def finish() -> None:
    """Finish the application, making sure any exception won't impact other closing tasks"""
    await protected_task(http_server.wait_stop())
    await protected_task(monitors_loader.wait_stop())
    await protected_task(databases.close())
    await protected_task(internal_database.close())
    await protected_task(stop_plugins_services())


async def main() -> None:
    if len(sys.argv) == 1:
        operation_modes = ["controller", "executor"]
    else:
        operation_modes = sys.argv[1:]

    await init(
        controller_enabled="controller" in operation_modes,
        executor_enabled="executor" in operation_modes,
    )

    modes = {
        "controller": controller.run,
        "executor": executor.run,
    }

    tasks = [modes[mode]() for mode in operation_modes]
    await asyncio.gather(*tasks)

    await finish()


if __name__ == "__main__":
    uvloop.run(main())

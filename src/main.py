# Still missing tests for main.py, so it's been ignored in the .coveragerc file

import asyncio
import logging
import sys

import components.controller as controller
import components.executor as executor
import components.http_server as http_server
import components.monitors_loader as monitors_loader
import components.task_manager as task_manager
import databases as databases
import internal_database as internal_database
import message_queue as message_queue
import plugins as plugins
import registry as registry
import utils.app as app
import utils.log as log
from base_exception import InitializationError
from utils.exception_handling import protected_task

_logger = logging.getLogger("main")


async def init(controller_enabled: bool, executor_enabled: bool) -> None:
    """Initialize the application dependencies. Some of the components will behave differently if
    they start with or without the controller."""
    # Log setup must be the first one
    log.setup()

    # Check database migrations
    await internal_database.check_database()

    # Application startup
    app.setup()
    registry.init()

    # Plugins must be initialized before the monitors loader as the register process will require
    # the plugins to be loaded
    plugins.load_plugins()
    await plugins.services.init_plugin_services(controller_enabled, executor_enabled)

    # Depends on internal database migrated
    await monitors_loader.init(controller_enabled)
    await http_server.init(controller_enabled)

    # The following modules depend on the plugins being loaded
    await databases.init()
    await message_queue.init()


async def finish(controller_enabled: bool, executor_enabled: bool) -> None:
    """Finish the application, making sure any exception won't impact other closing tasks"""
    await protected_task(_logger, http_server.wait_stop())
    await protected_task(_logger, databases.close())
    await protected_task(_logger, internal_database.close())
    await protected_task(
        _logger,
        plugins.services.stop_plugin_services(controller_enabled, executor_enabled),
    )


async def main() -> None:
    if len(sys.argv) == 1:
        operation_modes = ["controller", "executor"]
    else:
        operation_modes = sys.argv[1:]

    try:
        await init(
            controller_enabled="controller" in operation_modes,
            executor_enabled="executor" in operation_modes,
        )
    except InitializationError as e:
        _logger.error("Failed to initialize")
        _logger.error(e)
        return
    except Exception:
        _logger.error("Failed to initialize", exc_info=True)
        return

    modes = {
        "controller": controller.run,
        "executor": executor.run,
    }

    for mode in operation_modes:
        task_manager.create_task(modes[mode]())
    task_manager.create_task(monitors_loader.run())

    await task_manager.run()

    await finish(
        controller_enabled="controller" in operation_modes,
        executor_enabled="executor" in operation_modes,
    )


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import sys

import uvloop

import components.controller as controller
import components.executor as executor
import components.http_server as http_server
import components.monitors_loader as monitors_loader
import databases as databases
import internal_database as internal_database
import message_queue as message_queue
import registry as registry
import utils.app as app
import utils.log as log

_logger = logging.getLogger("main")


async def protected_task(task):
    try:
        await task
    except Exception:
        _logger.warning(f"Exception with task '{task}'")


async def init(controller_enabled: bool, executor_enabled: bool):
    """Initialize the application dependencies. Some of the components will behave differently if
    they start with or without the controller."""
    # Log setup must be the first one
    log.setup()
    app.setup()
    registry.init()
    await databases.init()
    # Depends on internal database migrated
    await monitors_loader.init(controller_enabled)
    await message_queue.init()
    await http_server.init(controller_enabled)


async def finish():
    """Finish the application, making sure any exception won't impact other closing tasks"""
    await protected_task(http_server.wait_stop())
    await protected_task(monitors_loader.wait_stop())
    await protected_task(databases.close())
    await protected_task(internal_database.close())


async def main():
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

    tasks = [
        modes[mode]()
        for mode in operation_modes
    ]
    await asyncio.gather(*tasks)

    await finish()


if __name__ == "__main__":
    uvloop.run(main())

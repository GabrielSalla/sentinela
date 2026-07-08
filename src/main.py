# Still missing tests for main.py, so it's been ignored in the .coveragerc file

import argparse
import asyncio
import logging
import sys
import traceback
from pathlib import Path

from pydantic import ValidationError

import commands
import components.controller as controller
import components.executor as executor
import components.heartbeat as heartbeat
import components.http_server as http_server
import components.monitors_loader as monitors_loader
import components.task_manager as task_manager
import databases as databases
import internal_database as internal_database
import message_queue as message_queue
import plugins as plugins
import registry as registry
import utils.app as app
import utils.environment_variables as environment_variables
import utils.log as log
from exceptions import InitializationError, MonitorValidationError
from utils.exception_handling import protected_task

CONTROLLER = "controller"
EXECUTOR = "executor"

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

    # Clean the environment variables (plugins should clean their environment variables)
    environment_variables.clean()


async def finish(controller_enabled: bool, executor_enabled: bool) -> None:
    """Finish the application, making sure any exception won't impact other closing tasks"""
    await protected_task(_logger, http_server.wait_stop())
    await protected_task(_logger, databases.close())
    await protected_task(_logger, internal_database.close())
    await protected_task(
        _logger,
        plugins.services.stop_plugin_services(controller_enabled, executor_enabled),
    )


async def run(args: argparse.Namespace) -> None:
    """Initialize and create the tasks for Sentinela execution"""
    operation_modes = set(args.modes) or {CONTROLLER, EXECUTOR}

    try:
        await init(
            controller_enabled=CONTROLLER in operation_modes,
            executor_enabled=EXECUTOR in operation_modes,
        )
    except InitializationError as e:
        _logger.error("Failed to initialize")
        _logger.error(e)
        return
    except Exception:
        _logger.error("Failed to initialize", exc_info=True)
        return

    modes = {
        CONTROLLER: controller.run,
        EXECUTOR: executor.run,
    }

    for mode in operation_modes:
        task_manager.create_task(modes[mode]())
    task_manager.create_task(heartbeat.run())
    task_manager.create_task(monitors_loader.run())

    await task_manager.run()

    await finish(
        controller_enabled=CONTROLLER in operation_modes,
        executor_enabled=EXECUTOR in operation_modes,
    )


async def validate_monitor(args: argparse.Namespace) -> None:
    """Validate a monitor and log the result"""
    log.setup()

    monitor_file = Path(args.monitor_file)

    # Read the file
    with open(monitor_file, "r") as file:
        monitor_code = file.read()

    # Validate the monitor
    try:
        await commands.monitor_code_validate(monitor_code, log_error=False)
        _logger.info("Monitor validated successfully")
    except ValidationError as e:
        _logger.error("Type validation error")

        for error in e.errors():
            location = ".".join([e.title] + [str(e) for e in error["loc"]])
            error_message = f"  {location}: {error['msg']}"
            _logger.error(error_message)
        sys.exit(1)
    except MonitorValidationError as e:
        _logger.error(e.get_error_message(include_monitor_name=False))
        sys.exit(1)
    except Exception:
        _logger.error(traceback.format_exc().strip())
        sys.exit(1)


async def register_monitor(args: argparse.Namespace) -> None:
    """Tries to register a monitor and log the result"""
    log.setup()

    monitor_name: str = args.monitor_name
    monitor_file = Path(args.monitor_file)
    additional_files = [Path(file_path) for file_path in args.additional_files]

    # Read the files
    with open(monitor_file, "r") as file:
        monitor_code = file.read()

    additional_files_content = {}
    for file_path in additional_files:
        with open(file_path, "r") as file:
            additional_files_content[file_path.stem] = file.read()

    # Register the monitor
    try:
        await commands.monitor_register(
            monitor_name, monitor_code, additional_files_content, log_error=False
        )
        _logger.info(f"Monitor {monitor_name} registered successfully")
    except ValidationError as e:
        _logger.error("Type validation error")

        for error in e.errors():
            location = ".".join([e.title] + [str(e) for e in error["loc"]])
            error_message = f"  {location}: {error['msg']}"
            _logger.error(error_message)
        sys.exit(1)
    except MonitorValidationError as e:
        _logger.error(e.get_error_message(include_monitor_name=False))
        sys.exit(1)
    except Exception:
        _logger.error(traceback.format_exc().strip())
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    """Parse and return the execution arguments"""
    parser = argparse.ArgumentParser(prog="sentinela")
    operation_parser = parser.add_subparsers(dest="operation", required=True)

    # Run parser
    run_parser = operation_parser.add_parser(
        "run", help="Execute Sentinela as a controller, executor or both."
    )
    run_parser.set_defaults(func=run)
    run_parser.add_argument(
        "modes",
        nargs="*",
        choices=[CONTROLLER, EXECUTOR],
        help=(
            "List of modes to run. If no modes are provided, both the controller and executor "
            "will run."
        ),
    )

    # Validate parser
    validate_parser = operation_parser.add_parser("validate", help="Validate a monitor")
    validate_parser.set_defaults(func=validate_monitor)
    validate_parser.add_argument("monitor_file", help="Path to the monitor .py code file.")

    # Register parser
    register_parser = operation_parser.add_parser("register", help="Register a monitor")
    register_parser.set_defaults(func=register_monitor)
    register_parser.add_argument("monitor_name", help="The monitor name to be registered.")
    register_parser.add_argument("monitor_file", help="Path to the monitor .py code file.")
    register_parser.add_argument(
        "additional_files",
        nargs="*",
        help="Optional. List of paths of additional files of the monitor.",
    )

    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    await args.func(args)


def start() -> None:
    asyncio.run(main())

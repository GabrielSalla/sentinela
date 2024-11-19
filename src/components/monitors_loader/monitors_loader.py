import asyncio
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Generator, cast

import src.module_loader as module_loader
import src.registry as registry
import src.utils.app as app
from src.components.monitors_loader.monitor_module_type import MonitorModule
from src.configs import configs
from src.models import CodeModule, Monitor
from src.options import ReactionOptions
from src.utils.exception_handling import catch_exceptions
from src.utils.time import now, time_since, time_until_next_trigger

_logger = logging.getLogger("monitor_loader")

MONITORS_PATH = "_monitors"
MONITORS_LOAD_PATH = "_monitors_load"
COOL_DOWN_TIME = 2

_task: asyncio.Task


@dataclass
class AdditionalFile:
    name: str
    path: Path


@dataclass
class MonitorFiles:
    monitor_name: str
    monitor_path: Path
    additional_files: list[AdditionalFile]


class MonitorValidationError(Exception):
    errors_found: list[str]

    def __init__(self, monitor_name: str, errors_found: list[str], *args: object) -> None:
        super().__init__(*args)
        self.monitor_name = monitor_name
        self.errors_found = errors_found

    def get_error_message(self) -> str:
        """Get the error message for the module validation errors"""
        error_message = f"Monitor '{self.monitor_name}' has the following errors:\n  "
        error_message += "\n  ".join(self.errors_found)
        return error_message


def _file_has_extension(file: str, extensions: list[str]) -> bool:
    """Check if a file has any of the given extensions"""
    return any(file.endswith(f".{extension}") for extension in extensions)


def _get_monitors_files_from_path(
        path: str,
        additional_file_extensions: list[str] | None = None
) -> Generator[MonitorFiles, None, None]:
    """Get all the monitor files from a path, including additional files present"""
    for root, folders, files in Path(path).walk():
        folder_name = root.stem

        if any(file_name == f"{folder_name}.py" for file_name in files):
            monitor_file = f"{folder_name}.py"
            monitor_path = root / monitor_file

            # Get the additional files, minus the monitor file (in case it happens to be in the
            # list)
            if additional_file_extensions is None:
                additional_file_extensions = []

            additional_files = []
            for file_name in files:
                if file_name == monitor_file:
                    continue
                if not _file_has_extension(file_name, additional_file_extensions):
                    continue

                additional_files.append(AdditionalFile(name=file_name, path=root / file_name))

            # Yield the monitor files
            monitor_files = MonitorFiles(
                monitor_name=folder_name,
                monitor_path=monitor_path,
                additional_files=additional_files
            )
            yield monitor_files


async def register_monitor(
        monitor_name: str,
        monitor_code: str,
        base_path: str | None = None,
        additional_files: dict[str, str] | None = None
) -> Monitor:
    """Register a monitor and its additional files"""
    if base_path is None:
        base_path = MONITORS_LOAD_PATH

    monitor_path = module_loader.create_module_files(
        monitor_name, monitor_code, base_path=base_path
    )
    module = module_loader.load_module_from_file(monitor_path)

    # Check the monitor module
    errors = module_loader.check_module(module=module)
    if len(errors) > 0:
        exception = MonitorValidationError(monitor_name=monitor_name, errors_found=errors)
        _logger.warning(exception.get_error_message())
        raise exception

    monitor = await Monitor.get_or_create(name=monitor_name)
    code_module = await CodeModule.get_or_create(monitor_id=monitor.id)
    code_module.code = monitor_code
    code_module.additional_files = additional_files or {}
    await code_module.save()

    return monitor


async def _register_monitors_from_path(
        path: str,
        internal: bool = False,
        additional_file_extensions: list[str] | None = None
):
    """Register monitors from a path, including their additional files"""
    for monitor_files in _get_monitors_files_from_path(path, additional_file_extensions):
        # Add the internal prefix to the monitor name
        monitor_name = monitor_files.monitor_name
        if internal:
            monitor_name = f"internal.{monitor_name}"

        # Read the monitor code
        with open(monitor_files.monitor_path, "r") as file:
            monitor_code = file.read()

        # Read the additional files
        additional_files = {}
        for additional_file in monitor_files.additional_files:
            with open(additional_file.path, "r") as file:
                additional_files[additional_file.name] = file.read()

        with catch_exceptions(_logger):
            await register_monitor(
                monitor_name=monitor_name,
                monitor_code=monitor_code,
                additional_files=additional_files,
            )


async def _register_monitors():
    """Register internal monitors and sample monitors, if enabled"""
    await _register_monitors_from_path(
        configs.internal_monitors_path, internal=True, additional_file_extensions=["sql"]
    )

    if configs.load_sample_monitors:
        await _register_monitors_from_path(configs.sample_monitors_path)


def _configure_monitor(monitor_module: MonitorModule):
    """Make the necessary configurations to the monitor's attributes"""
    # Add an empty reaction option if it was not configured
    if getattr(monitor_module, "reaction_options", None) is None:
        monitor_module.reaction_options = ReactionOptions()

    # Add an empty notifications option  if it was not configured
    if getattr(monitor_module, "notification_options", None) is None:
        monitor_module.notification_options = []

    # Add all notifications reactions to the monitor's reactions
    for notification in monitor_module.notification_options:
        for event_name, reactions in notification.reactions_list():
            monitor_module.reaction_options[event_name].extend(reactions)


async def _load_monitors():
    """Load all enabled monitors from the database and add them to the registry. If any of the
    monitor's modules fails to load, the monitor will not be added to the registry"""
    registry.monitors_ready.clear()

    loaded_monitors = await Monitor.get_all(Monitor.enabled.is_(True))
    monitors_ids = [monitor.id for monitor in loaded_monitors]

    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))
    code_modules_map = {
        code_module.monitor_id: code_module
        for code_module in code_modules
    }

    _logger.info(f"Monitors found: {len(loaded_monitors)}")

    # To load the monitors safely, first create all the files and then import them
    # Loading right after writing the files can result in an error where the Monitor module is not
    # found
    monitors_paths = {}
    for monitor in loaded_monitors:
        with catch_exceptions(_logger):
            code_module = code_modules_map.get(monitor.id)
            if code_module is None:
                await monitor.set_enabled(False)
                _logger.warning(
                    f"Monitor '{monitor.name}' has no code module, it will be disabled"
                )
                continue

            monitors_paths[monitor.id] = module_loader.create_module_files(
                module_name=monitor.name,
                module_code=code_module.code,
                additional_files=code_module.additional_files,
            )

    for monitor in loaded_monitors:
        with catch_exceptions(_logger):
            monitor_path = monitors_paths.get(monitor.id)
            if monitor_path is None:
                continue

            monitor_module = cast(
                MonitorModule, module_loader.load_module_from_file(monitor_path)
            )
            _configure_monitor(monitor_module)

            registry.add_monitor(monitor.id, monitor.name, monitor_module)

    registry.monitors_ready.set()
    registry.monitors_pending.clear()


async def _run():
    """Monitors loading loop, loading them recurrently. Stops automatically when the app stops"""
    last_load_time: datetime | None = None

    while app.running():
        with catch_exceptions(_logger):
            await _load_monitors()
            last_load_time = now()

            # The sleep task will start 2 seconds earlier to try to load all monitors before the
            # next controller and executor loops start
            sleep_task = asyncio.create_task(
                app.sleep(time_until_next_trigger(configs.monitors_load_schedule) - 2)
            )
            registry_pending_task = asyncio.create_task(registry.monitors_pending.wait())

            done, pending = await asyncio.wait(
                [sleep_task, registry_pending_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

            # Check if the last load time was recent, to prevent reloading the monitors too often
            time_since_last_load = time_since(last_load_time)
            if time_since_last_load < COOL_DOWN_TIME:
                await app.sleep(COOL_DOWN_TIME - time_since_last_load)


async def init(controller_enabled: bool):
    """Load the internal monitors and sample monitors if controller is enabled, and start the
    monitors load task"""
    if controller_enabled:
        await _register_monitors()

    global _task
    _task = asyncio.create_task(_run())


async def wait_stop():
    """Wait for the Monitors load task to finish"""
    global _task
    await _task
    _logger.info("Removing temporary monitors paths")
    shutil.rmtree(MONITORS_LOAD_PATH, ignore_errors=True)
    shutil.rmtree(MONITORS_PATH, ignore_errors=True)

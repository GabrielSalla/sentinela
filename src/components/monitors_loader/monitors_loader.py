import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Generator, cast

from pydantic.dataclasses import dataclass

import module_loader as module_loader
import registry as registry
import utils.app as app
from configs import configs
from data_models.monitor_options import ReactionOptions
from models import CodeModule, Monitor
from utils.async_tools import do_concurrently
from utils.exception_handling import catch_exceptions
from utils.time import now, time_since, time_until_next_trigger

from .monitor_module_type import MonitorModule

_logger = logging.getLogger("monitor_loader")

RELATIVE_PATH = "src"
MONITORS_PATH = "_monitors"
MONITORS_LOAD_PATH = "_monitors_load"
EARLY_LOAD_TIME = 5
COOL_DOWN_TIME = 2

_task: asyncio.Task[Any]


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


def check_monitor(
    monitor_name: str, monitor_code: str, base_path: str | None = None, log_error: bool = False
) -> None:
    """Check if a monitor module is valid without registering it"""
    module_path, module = module_loader.load_module_from_string(
        module_name=monitor_name, module_code=monitor_code, base_path=base_path
    )

    errors = module_loader.check_module(module=module)
    module_loader.remove_module(module_name=module_loader.make_module_name(module_path))
    if len(errors) > 0:
        exception = MonitorValidationError(monitor_name=monitor_name, errors_found=errors)
        if log_error:
            _logger.error(exception.get_error_message())
        raise exception


async def register_monitor(
    monitor_name: str,
    monitor_code: str,
    base_path: str | None = None,
    additional_files: dict[str, str] | None = None,
) -> Monitor:
    """Register a monitor and its additional files"""
    check_monitor(
        base_path=base_path, monitor_name=monitor_name, monitor_code=monitor_code, log_error=True
    )

    monitor = await Monitor.get_or_create(name=monitor_name)
    code_module = await CodeModule.get_or_create(monitor_id=monitor.id)
    code_module.code = monitor_code
    code_module.additional_files = additional_files or {}
    code_module.registered_at = now()
    await code_module.save()

    return monitor


def _get_monitors_files_from_path(
    path: str, additional_file_extensions: list[str] | None = None
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
                additional_files=additional_files,
            )
            yield monitor_files


async def _register_monitors_from_path(
    path: str, internal: bool = False, additional_file_extensions: list[str] | None = None
) -> None:
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
            try:
                await register_monitor(
                    monitor_name=monitor_name,
                    monitor_code=monitor_code,
                    additional_files=additional_files,
                )
            except MonitorValidationError:
                _logger.error(f"Monitor '{monitor_name}' not registered")


async def _register_monitors() -> None:
    """Register internal monitors and sample monitors, if enabled"""
    await _register_monitors_from_path(
        configs.internal_monitors_path, internal=True, additional_file_extensions=["sql"]
    )

    if configs.load_sample_monitors:
        await _register_monitors_from_path(configs.sample_monitors_path)


def _configure_monitor(monitor_module: MonitorModule) -> None:
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


async def _disable_monitor(monitor: Monitor) -> None:
    """Disable a monitor"""
    await monitor.set_enabled(False)
    _logger.warning(f"Monitor '{monitor}' has no code module, it will be disabled")


async def _disable_monitors_without_code_modules() -> None:
    """Disable all monitors that don't have a code module"""
    enabled_monitors = await Monitor.get_raw([Monitor.id], [Monitor.enabled.is_(True)])
    monitors_ids = {monitor_id for (monitor_id,) in enabled_monitors}

    code_modules = await CodeModule.get_raw([CodeModule.monitor_id], [CodeModule.code.is_not(None)])
    code_modules_monitor_ids = {monitor_id for (monitor_id,) in code_modules}

    monitors_to_disable = await Monitor.get_all(
        Monitor.id.in_(monitors_ids - code_modules_monitor_ids)
    )
    await do_concurrently(*[_disable_monitor(monitor) for monitor in monitors_to_disable])


async def _get_monitors_to_load(
    last_load_time: datetime | None,
) -> tuple[dict[int, Monitor], list[CodeModule]]:
    """Get all the monitors that need to be loaded"""
    # Get all enabled monitors
    loaded_monitors = await Monitor.get_all(Monitor.enabled.is_(True))
    monitors = {monitor.id: monitor for monitor in loaded_monitors}

    # Get all code modules that were updated since the last load time
    # Add a time delta to have some room for code modules that updated right before the last load
    if last_load_time is None:
        reference_timestamp = None
    else:
        reference_timestamp = last_load_time - timedelta(seconds=15)

    updated_code_modules = await CodeModule.get_updated_code_modules(
        monitors_ids=list(monitors.keys()),
        reference_timestamp=reference_timestamp,
    )
    code_modules = [code_module for code_module in updated_code_modules]

    # Add monitors that are enabled but aren't in the registry
    registry_monitors_ids = set(registry.get_monitors_ids())
    update_monitors_ids = {code_module.monitor_id for code_module in updated_code_modules}
    pending_monitors = set(monitors.keys()) - registry_monitors_ids - update_monitors_ids
    if len(pending_monitors) > 0:
        code_modules.extend(await CodeModule.get_all(CodeModule.monitor_id.in_(pending_monitors)))

    return monitors, code_modules


async def _load_monitors() -> None:
    """Load all enabled monitors from the database and add them to the registry. If any of the
    monitor's modules fails to load, the monitor will not be added to the registry"""
    registry.monitors_ready.clear()

    loaded_monitors = await Monitor.get_all(Monitor.enabled.is_(True))
    monitors_ids = [monitor.id for monitor in loaded_monitors]

    code_modules = await CodeModule.get_all(CodeModule.monitor_id.in_(monitors_ids))
    code_modules_map = {code_module.monitor_id: code_module for code_module in code_modules}

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
                _logger.warning(f"Monitor '{monitor.name}' has no code module, it will be disabled")
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

            monitor_module = cast(MonitorModule, module_loader.load_module_from_file(monitor_path))
            _configure_monitor(monitor_module)

            registry.add_monitor(monitor.id, monitor.name, monitor_module)

    registry.monitors_ready.set()
    registry.monitors_pending.clear()


async def _run() -> None:
    """Monitors loading loop, loading them recurrently. Stops automatically when the app stops"""
    last_load_time: datetime

    while app.running():
        with catch_exceptions(_logger):
            await _load_monitors()
            last_load_time = now()

            # The sleep task will start seconds earlier to try to load all monitors before the
            # next controller and executor loops start
            # Adding the EARLY_LOAD_TIME to the datetime reference to make sure the next trigger
            # won't be the same one that triggered the current one
            # Example: the expected time to reload is 10:00 but 5 seconds were subtracted
            # (the early load) from the sleep time. If the monitors were loaded in less than 5
            # seconds, the 'time_until_next_trigger' function would return 10:00 again, instead of
            # the expected trigger time
            sleep_time = time_until_next_trigger(
                configs.monitors_load_schedule,
                datetime_reference=now() + timedelta(seconds=EARLY_LOAD_TIME),
            )
            sleep_task = asyncio.create_task(app.sleep(sleep_time))
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


async def init(controller_enabled: bool) -> None:
    """Load the internal monitors and sample monitors if controller is enabled, and start the
    monitors load task"""
    if controller_enabled:
        await _register_monitors()

    global _task
    _task = asyncio.create_task(_run())


async def wait_stop() -> None:
    """Wait for the Monitors load task to finish"""
    global _task
    await _task
    _logger.info("Removing temporary monitors paths")
    shutil.rmtree(Path(RELATIVE_PATH) / MONITORS_LOAD_PATH, ignore_errors=True)
    shutil.rmtree(Path(RELATIVE_PATH) / MONITORS_PATH, ignore_errors=True)

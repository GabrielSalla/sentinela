import logging
from types import ModuleType

from utils.exception_handling import protected_task

_logger = logging.getLogger("plugins.services")


async def _plugin_service_run(
    plugin_name: str,
    plugin: ModuleType,
    function_name: str,
    controller_enabled: bool,
    executor_enabled: bool,
) -> None:
    """Run a function of a plugin service, used to initialize or stop the services"""
    plugin_services = getattr(plugin, "services", None)
    if plugin_services is None:
        _logger.info(f"Plugin '{plugin_name}' has no services")
        return

    plugin_services_names = getattr(plugin_services, "__all__", None)
    if plugin_services_names is None:
        _logger.warning(f"Plugin '{plugin_name}' has no '__all__' attribute in services")
        return

    for service_name in plugin_services_names:
        service = getattr(plugin_services, service_name, None)
        if service is None:
            _logger.warning(f"Service '{plugin_name}.{service_name}' not found")
            continue

        target_function = getattr(service, function_name, None)
        if target_function is None:
            _logger.warning(
                f"Service '{plugin_name}.{service_name}' has no '{function_name}' function"
            )
            continue

        _logger.info(f"Running '{plugin_name}.{service_name}.{function_name}'")
        await protected_task(_logger, target_function(controller_enabled, executor_enabled))


async def init_plugin_services(controller_enabled: bool, executor_enabled: bool) -> None:
    """Initialize the plugins services"""
    # Import loaded plugins here after all the plugins are loaded
    from . import loaded_plugins

    for plugin_name, plugin in loaded_plugins.items():
        _logger.info(f"Starting plugin '{plugin_name}' services")
        await _plugin_service_run(plugin_name, plugin, "init", controller_enabled, executor_enabled)


async def stop_plugin_services(controller_enabled: bool, executor_enabled: bool) -> None:
    """Stop the plugins services"""
    # Import loaded plugins here after all the plugins are loaded
    from . import loaded_plugins

    for plugin_name, plugin in loaded_plugins.items():
        _logger.info(f"Stopping plugin '{plugin_name}' services")
        await _plugin_service_run(plugin_name, plugin, "stop", controller_enabled, executor_enabled)

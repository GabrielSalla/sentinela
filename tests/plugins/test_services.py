from unittest.mock import AsyncMock

import pytest

import plugins
from plugins.services import _plugin_service_run, init_plugin_services, stop_plugin_services
from tests.test_utils import assert_message_in_log, assert_message_not_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="module", autouse=True)
def set_loaded_plugins(monkeypatch_module):
    """Set the loaded plugins for the tests"""
    monkeypatch_module.setattr(plugins, "loaded_plugins", {}, raising=False)


@pytest.mark.parametrize("function_name", ["init", "stop", "other"])
@pytest.mark.parametrize("controller_enabled, executor_enabled", [(True, False), (False, True)])
async def test_plugin_service_run_single_service(
    caplog, mocker, function_name, controller_enabled, executor_enabled
):
    """'_plugin_service_run' should run the provided function of all the plugin services"""

    class Plugin:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

                @staticmethod
                async def stop(controller_enabled, executor_enabled):
                    pass

                @staticmethod
                async def other(controller_enabled, executor_enabled):
                    pass

    init_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "init")
    stop_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "stop")
    other_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "other")

    await _plugin_service_run(
        "plugin_name",
        Plugin,
        function_name,
        controller_enabled,
        executor_enabled,
    )

    if function_name == "init":
        init_spy.assert_awaited_once_with(controller_enabled, executor_enabled)
        assert_message_in_log(caplog, "Running 'plugin_name.service_type.init'")
    else:
        init_spy.assert_not_called()

    if function_name == "stop":
        stop_spy.assert_awaited_once_with(controller_enabled, executor_enabled)
        assert_message_in_log(caplog, "Running 'plugin_name.service_type.stop'")
    else:
        stop_spy.assert_not_called()
        assert_message_not_in_log(caplog, "Running 'plugin_name.service_type.stop'")

    if function_name == "other":
        other_spy.assert_awaited_once_with(controller_enabled, executor_enabled)
        assert_message_in_log(caplog, "Running 'plugin_name.service_type.other'")
    else:
        other_spy.assert_not_called()
        assert_message_not_in_log(caplog, "Running 'plugin_name.service_type.other'")


@pytest.mark.parametrize(
    "enabled_services",
    [
        ("service_type1", "service_type2"),
        ("service_type1",),
        ("service_type2",),
        tuple(),
    ],
)
async def test_plugin_service_run_multiple_services(caplog, mocker, enabled_services):
    """'_plugin_service_run' should run the provided function of all the plugin services when there
    are multiple services"""

    class Plugin:
        class services:
            __all__ = enabled_services

            class service_type1:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

            class service_type2:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    init_spy1: AsyncMock = mocker.spy(Plugin.services.service_type1, "init")
    init_spy2: AsyncMock = mocker.spy(Plugin.services.service_type2, "init")

    await _plugin_service_run("plugin_name", Plugin, "init", True, True)

    if "service_type1" in enabled_services:
        init_spy1.assert_awaited_once_with(True, True)
        assert_message_in_log(caplog, "Running 'plugin_name.service_type1.init'")
    else:
        init_spy1.assert_not_called()
        assert_message_not_in_log(caplog, "Running 'plugin_name.service_type1.init'")

    if "service_type2" in enabled_services:
        init_spy2.assert_awaited_once_with(True, True)
        assert_message_in_log(caplog, "Running 'plugin_name.service_type2.init'")
    else:
        init_spy2.assert_not_called()
        assert_message_not_in_log(caplog, "Running 'plugin_name.service_type2.init'")


async def test_init_plugins_no_services(caplog):
    """'_plugin_service_run' should handle plugins with no services"""

    class Plugin:
        pass

    await _plugin_service_run("plugin_name", Plugin, "init", True, False)

    assert_message_in_log(caplog, "Plugin 'plugin_name' has no services")


async def test_plugin_service_run_no_all(caplog, mocker):
    """'_plugin_service_run' should handle plugins with no '__all__' list"""

    class Plugin:
        class services:
            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    init_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "init")

    await _plugin_service_run("plugin_name", Plugin, "init", True, False)

    assert_message_in_log(caplog, "Plugin 'plugin_name' has no '__all__' attribute in services")
    init_spy.assert_not_called()


async def test_plugin_service_run_invalid_service(caplog, mocker):
    """'_plugin_service_run' should handle invalid services in the '__all__' list"""

    class Plugin:
        class services:
            __all__ = ["not_a_service"]

            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    init_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "init")

    await _plugin_service_run("plugin_name", Plugin, "init", True, False)

    assert_message_in_log(caplog, "Service 'plugin_name.not_a_service' not found")
    init_spy.assert_not_called()
    assert_message_not_in_log(caplog, "Service 'plugin_name.service_type' initialized")


async def test_plugin_service_run_no_init_function(caplog):
    """'_plugin_service_run' should skip services without an 'init' function"""

    class Plugin:
        class services:
            __all__ = ["service_type"]

            class service_type:
                pass

    await _plugin_service_run("plugin_name", Plugin, "init", True, False)
    assert_message_in_log(caplog, "Service 'plugin_name.service_type' has no 'init' function")


async def test_plugin_service_run_error(caplog):
    """'_plugin_service_run' should handle errors in the plugin service function"""

    class Plugin:
        class services:
            __all__ = ["service_type1", "service_type2"]

            class service_type1:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    raise Exception("Error in service_type1")

            class service_type2:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    raise Exception("Error in service_type2")

    await _plugin_service_run("plugin_name", Plugin, "init", True, False)

    assert_message_in_log(caplog, "Exception with task", count=2)
    assert_message_in_log(caplog, "Error in service_type1")
    assert_message_in_log(caplog, "Error in service_type2")


@pytest.mark.parametrize(
    "controller_enabled, executor_enabled",
    [(False, False), (True, True), (True, False), (False, True)],
)
async def test_init_plugin_services(
    caplog, mocker, monkeypatch, controller_enabled, executor_enabled
):
    """'init_plugin_services' should initialize services for all loaded plugins"""

    class Plugin:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)
    init_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "init")

    await init_plugin_services(controller_enabled, executor_enabled)

    assert_message_in_log(caplog, "Starting plugin 'plugin_name'")
    init_spy.assert_awaited_once_with(controller_enabled, executor_enabled)


async def test_init_plugin_services_multiple_plugins(caplog, mocker, monkeypatch):
    """'init_plugin_services' should initialize services for all loaded plugins"""

    class Plugin1:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    class Plugin2:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def init(controller_enabled, executor_enabled):
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name1", Plugin1)
    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name2", Plugin2)

    init_spy1: AsyncMock = mocker.spy(Plugin1.services.service_type, "init")
    init_spy2: AsyncMock = mocker.spy(Plugin2.services.service_type, "init")

    await init_plugin_services(True, False)

    assert_message_in_log(caplog, "Starting plugin 'plugin_name1'")
    assert_message_in_log(caplog, "Starting plugin 'plugin_name2'")
    init_spy1.assert_awaited_once_with(True, False)
    init_spy2.assert_awaited_once_with(True, False)


async def test_init_plugin_services_no_plugins(caplog):
    """'init_plugin_services' should handle no loaded plugins"""
    await init_plugin_services(False, False)

    assert_message_not_in_log(caplog, "Starting plugin")


@pytest.mark.parametrize("controller_enabled, executor_enabled", [(True, False), (False, True)])
async def test_stop_plugin_services(
    caplog, mocker, monkeypatch, controller_enabled, executor_enabled
):
    """'stop_plugin_services' should stop services for all loaded plugins"""

    class Plugin:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def stop(controller_enabled, executor_enabled):
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)
    stop_spy: AsyncMock = mocker.spy(Plugin.services.service_type, "stop")

    await stop_plugin_services(controller_enabled, executor_enabled)

    stop_spy.assert_awaited_once_with(controller_enabled, executor_enabled)
    assert_message_in_log(caplog, "Stopping plugin 'plugin_name'")


async def test_stop_plugin_services_multiple_plugins(mocker, monkeypatch):
    """'stop_plugin_services' should stop services for all loaded plugins"""

    class Plugin1:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def stop(controller_enabled, executor_enabled):
                    pass

    class Plugin2:
        class services:
            __all__ = ["service_type"]

            class service_type:
                @staticmethod
                async def stop(controller_enabled, executor_enabled):
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name1", Plugin1)
    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name2", Plugin2)

    stop_spy1: AsyncMock = mocker.spy(Plugin1.services.service_type, "stop")
    stop_spy2: AsyncMock = mocker.spy(Plugin2.services.service_type, "stop")

    await stop_plugin_services(True, False)

    stop_spy1.assert_awaited_once_with(True, False)
    stop_spy2.assert_awaited_once_with(True, False)


async def test_stop_plugin_services_no_plugins(caplog):
    """'stop_plugin_services' should handle no loaded plugins"""
    await stop_plugin_services(False, False)

    assert_message_not_in_log(caplog, "Stopping plugin")

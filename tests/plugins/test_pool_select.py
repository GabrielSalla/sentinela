from typing import Any

import pytest

import plugins
import plugins.pool_select as pool_select
from tests.test_utils import assert_message_in_log


class PoolMock:
    PATTERNS: list[str]
    name: str = ""

    def __init__(self, dsn: str, name: str, **configs: Any) -> None: ...

    async def init(self) -> None: ...

    async def execute(
        self, sql: str, *args: str | int | float | bool | list[str] | list[int] | list[float] | None
    ) -> None: ...

    async def fetch(
        self,
        sql: str,
        *args: str | int | float | bool | list[str] | list[int] | list[float] | None,
        acquire_timeout: int,
        query_timeout: int,
    ) -> list[dict[str, Any]]: ...

    async def close(self) -> None: ...


@pytest.fixture(scope="module", autouse=True)
def set_loaded_plugins(monkeypatch_module):
    """Set the loaded plugins for the tests"""
    monkeypatch_module.setattr(plugins, "loaded_plugins", {}, raising=False)


def test_get_plugin_pool(monkeypatch):
    """'get_plugin_pool' should get the pool from the defined plugin"""

    class Plugin:
        class pools:
            __all__ = ["pool_type"]

            class pool_type(PoolMock):
                PATTERNS = ["pattern"]

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    class OtherPlugin:
        class pools:
            __all__ = ["another_pool_type", "other_pool_type"]

            class another_pool_type(PoolMock):
                PATTERNS = ["another_pattern"]

            class other_pool_type(PoolMock):
                PATTERNS = ["other_pattern"]

    monkeypatch.setitem(plugins.loaded_plugins, "other_plugin_name", OtherPlugin)

    pool = pool_select.get_plugin_pool("pattern")
    assert pool == Plugin.pools.pool_type

    pool = pool_select.get_plugin_pool("other_pattern")
    assert pool == OtherPlugin.pools.other_pool_type

    pool = pool_select.get_plugin_pool("another_pattern")
    assert pool == OtherPlugin.pools.another_pool_type


def test_get_plugin_pool_plugin_not_loaded(caplog):
    """'get_plugin_pool' should return 'None' when the plugin is not loaded"""
    assert pool_select.get_plugin_pool("pattern") is None
    assert_message_in_log(caplog, "Unable to find pool for pattern 'pattern'")


def test_get_plugin_pool_plugin_no_pools(caplog, monkeypatch):
    """'get_plugin_pool' should return None when the plugin has no pools"""

    class Plugin:
        pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    assert pool_select.get_plugin_pool("pattern") is None
    assert_message_in_log(caplog, "Unable to find pool for pattern 'pattern'")


def test_get_plugin_pool_class_not_found(caplog, monkeypatch):
    """'get_plugin_pool' should return None when the pool class is not found"""

    class Plugin:
        class pools:
            __all__ = ["pool_type"]

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    assert pool_select.get_plugin_pool("pattern") is None
    assert_message_in_log(caplog, "Plugin 'plugin_name' pool 'pool_type' class not found")


def test_get_plugin_pool_invalid_interface(caplog, monkeypatch):
    """'get_plugin_pool' should return None when the pool class has invalid interface"""

    class Plugin:
        class pools:
            __all__ = ["pool_type"]

            class pool_type:
                PATTERNS = ["some_pattern"]

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    assert pool_select.get_plugin_pool("some_pattern") is None
    assert_message_in_log(
        caplog,
        "Plugin 'plugin_name' pool 'pool_type' accepts the type 'some_pattern' "
        "but has invalid interface",
    )

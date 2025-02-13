import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import plugins as plugins
import plugins.plugins_loader as plugins_loader
from configs import configs
from tests.test_utils import assert_message_in_log, assert_message_not_in_log


@pytest.fixture(scope="function")
def plugins_directory(temp_dir: Path) -> Path:
    """Create a directory with plugins for testing"""
    plugins_dir = temp_dir / "plugins"
    plugins_dir.mkdir()

    for i in range(1, 4):
        plugin_dir = plugins_dir / f"plugin{i}"
        plugin_dir.mkdir()
        init_file_dir = plugin_dir / "__init__.py"
        with open(init_file_dir, "w") as f:
            f.write(f"a = {i * 10}")

    pycache_dir = plugins_dir / "__pycache__"
    pycache_dir.mkdir()

    return plugins_dir


@pytest.mark.parametrize(
    "enabled_plugins",
    [
        ["plugin1", "plugin2", "plugin3"],
        ["plugin1", "plugin2"],
        ["plugin1", "plugin3"],
        ["plugin2", "plugin3"],
        ["plugin1"],
        ["plugin2"],
        ["plugin3"],
        [],
    ],
)
def test_load_plugins(monkeypatch, plugins_directory, enabled_plugins):
    """'load_plugins' should load all plugins from the directory, loading only the enabled
    plugins"""
    monkeypatch.setattr(configs, "plugins", enabled_plugins)

    loaded_plugins = plugins_loader.load_plugins(str(plugins_directory))

    if "plugin1" in enabled_plugins:
        assert loaded_plugins["plugin1"].a == 10
    else:
        assert "plugin1" not in loaded_plugins
    if "plugin2" in enabled_plugins:
        assert loaded_plugins["plugin2"].a == 20
    else:
        assert "plugin2" not in loaded_plugins
    if "plugin3" in enabled_plugins:
        assert loaded_plugins["plugin3"].a == 30
    else:
        assert "plugin3" not in loaded_plugins

    assert "__pycache__" not in loaded_plugins


@pytest.mark.parametrize(
    "enabled_plugins",
    [
        ["plugin1", "plugin2", "plugin3"],
        ["plugin1", "plugin2"],
        ["plugin1", "plugin3"],
        ["plugin2", "plugin3"],
        ["plugin1"],
        ["plugin2"],
        ["plugin3"],
        [],
    ],
)
def test_load_plugins_with_error(caplog, monkeypatch, plugins_directory, enabled_plugins):
    """'load_plugins' should catch exceptions and log error messages when a plugin cannot be
    loaded"""
    monkeypatch.setattr(configs, "plugins", enabled_plugins)

    with open(plugins_directory / "plugin1" / "__init__.py", "w") as file:
        file.write("raise Exception('Some import error')")

    loaded_plugins = plugins_loader.load_plugins(str(plugins_directory))

    if "plugin1" in enabled_plugins:
        assert "plugin1" not in loaded_plugins
        assert_message_in_log(caplog, "Error loading plugin 'plugin1'")
        assert_message_in_log(caplog, "Exception: Some import error")
    else:
        assert "plugin1" not in loaded_plugins
        assert_message_not_in_log(caplog, "Error loading plugin 'plugin1'")
        assert_message_not_in_log(caplog, "Exception: Some import error")
    if "plugin2" in enabled_plugins:
        assert loaded_plugins["plugin2"].a == 20
    else:
        assert "plugin2" not in loaded_plugins
    if "plugin3" in enabled_plugins:
        assert loaded_plugins["plugin3"].a == 30
    else:
        assert "plugin3" not in loaded_plugins


def test_load_plugins_default_path(mocker):
    """'load_plugins' should use the default plugins path if none is provided"""
    os_listdir_spy: MagicMock = mocker.spy(os, "listdir")

    plugins_loader.load_plugins()

    plugins_path = Path("src/plugins")
    os_listdir_spy.assert_called_once_with(plugins_path)


def test_init_load_plugins():
    """'load_plugins' from the init file should load all existing plugins"""
    plugins.load_plugins()
    assert "slack" in plugins.loaded_plugins

import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock

import plugins as plugins
import plugins.plugins_loader as plugins_loader
from tests.test_utils import assert_message_in_log


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
            f.write(f"a = {i*10}")

    pycache_dir = plugins_dir / "__pycache__"
    pycache_dir.mkdir()

    return plugins_dir


def test_load_plugins(plugins_directory):
    """'load_plugins' should load all plugins from the directory"""
    loaded_plugins = plugins_loader.load_plugins(str(plugins_directory))
    assert loaded_plugins["plugin1"].a == 10
    assert loaded_plugins["plugin2"].a == 20
    assert loaded_plugins["plugin3"].a == 30
    assert "__pycache__" not in loaded_plugins


def test_load_plugins_with_error(caplog, plugins_directory):
    """'load_plugins' should catch exceptions and log error messages when a plugin cannot be
    loaded"""
    with open(plugins_directory / "plugin1" / "__init__.py", "w") as file:
        file.write("raise Exception('Some import error')")

    loaded_plugins = plugins_loader.load_plugins(str(plugins_directory))

    assert_message_in_log(caplog, "Error loading plugin 'plugin1'")
    assert_message_in_log(caplog, "Exception: Some import error")
    assert loaded_plugins["plugin2"].a == 20
    assert loaded_plugins["plugin3"].a == 30


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

import pytest

import plugins
import plugins.queue_select as queue_select


@pytest.fixture(scope="module", autouse=True)
def set_loaded_plugins(monkeypatch_module):
    """Set the loaded plugins for the tests"""
    monkeypatch_module.setattr(plugins, "loaded_plugins", {}, raising=False)


def test_get_plugin_queue(monkeypatch):
    """'get_plugin_queue' should get the queue from the defined plugin"""

    class Plugin:
        class queues:
            class queue_type:
                class Queue:
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    class OtherPlugin:
        class queues:
            class other_queue_type:
                class Queue:
                    pass

    monkeypatch.setitem(plugins.loaded_plugins, "other_plugin_name", OtherPlugin)

    queue = queue_select.get_plugin_queue("plugin.plugin_name.queue_type")
    assert queue == Plugin.queues.queue_type.Queue

    queue = queue_select.get_plugin_queue("plugin.other_plugin_name.other_queue_type")
    assert queue == OtherPlugin.queues.other_queue_type.Queue


def test_get_plugin_queue_plugin_not_loaded():
    """'get_plugin_queue' should raise a ValueError when the plugin is not loaded"""
    with pytest.raises(ValueError, match="Plugin 'plugin_name' not loaded"):
        queue_select.get_plugin_queue("plugin.plugin_name.queue_type")


def test_get_plugin_queue_plugin_no_queues(monkeypatch):
    """'get_plugin_queue' should raise a ValueError when the plugin has no queues"""

    class Plugin:
        pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    with pytest.raises(ValueError, match="Plugin 'plugin_name' has no queues"):
        queue_select.get_plugin_queue("plugin.plugin_name.queue_type")


def test_get_plugin_queue_plugin_no_queue_type(monkeypatch):
    """'get_plugin_queue' should raise a ValueError when the plugin does not provided the desired
    queue type"""

    class Plugin:
        class queues:
            pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    with pytest.raises(ValueError, match="Plugin 'plugin_name' has no queue 'queue_type'"):
        queue_select.get_plugin_queue("plugin.plugin_name.queue_type")


def test_get_plugin_queue_plugin_no_queue(monkeypatch):
    """'get_plugin_queue' should raise a ValueError when the plugin queue does not implement the
    'Queue' class"""

    class Plugin:
        class queues:
            class queue_type:
                pass

    monkeypatch.setitem(plugins.loaded_plugins, "plugin_name", Plugin)

    expected_message = "Plugin 'plugin_name' queue 'queue_type' has no 'Queue' class"
    with pytest.raises(ValueError, match=expected_message):
        queue_select.get_plugin_queue("plugin.plugin_name.queue_type")

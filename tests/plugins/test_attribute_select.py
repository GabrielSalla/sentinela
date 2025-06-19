import pytest

from plugins.attribute_select import get_plugin_attribute


def test_get_plugin_attribute_success(monkeypatch):
    """'get_plugin_attribute' should return the attribute value when the path is valid"""

    class MockPlugin:
        class MockAttr1:
            class MockAttr2:
                value = "test_value"

    monkeypatch.setattr("plugins.loaded_plugins", {"my_plugin": MockPlugin}, raising=False)

    result = get_plugin_attribute("plugin.my_plugin.MockAttr1.MockAttr2.value")
    assert result == "test_value"


@pytest.mark.parametrize("attribute_path", ["plugin.a", "plugin.a.b"])
def test_get_plugin_attribute_path_too_short(attribute_path):
    """'get_plugin_attribute' should raise ValueError when the attribute path is too short"""
    expected_error = "Attribute path must specify a plugin and at least two attributes"
    with pytest.raises(ValueError, match=expected_error):
        get_plugin_attribute(attribute_path)


def test_get_plugin_attribute_plugin_not_loaded(monkeypatch):
    """'get_plugin_attribute' should raise ValueError when the plugin is not loaded"""
    monkeypatch.setattr("plugins.loaded_plugins", {"other_plugin": "nothing here"}, raising=False)

    expected_error = "Plugin 'my_plugin' not loaded"
    with pytest.raises(ValueError, match=expected_error):
        get_plugin_attribute("plugin.my_plugin.attr1.attr2.value")


@pytest.mark.parametrize(
    "attribute_path, expected_error_path",
    [
        ("plugin.my_plugin.attr1.attr2.attr3", "attr1"),
        ("plugin.my_plugin.MockAttr1.attr2", "MockAttr1.attr2"),
        ("plugin.my_plugin.MockAttr1.attr2.attr3", "MockAttr1.attr2"),
    ],
)
def test_get_plugin_attribute_attribute_not_found(monkeypatch, attribute_path, expected_error_path):
    """'get_plugin_attribute' should raise ValueError when an intermediate attribute is not found"""

    class MockPlugin:
        class MockAttr1:
            pass

    monkeypatch.setattr("plugins.loaded_plugins", {"my_plugin": MockPlugin}, raising=False)

    expected_error = f"Plugin 'my_plugin' has no attribute '{expected_error_path}'"
    with pytest.raises(ValueError, match=expected_error):
        get_plugin_attribute(attribute_path)

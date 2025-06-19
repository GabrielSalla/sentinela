from typing import Any
from unittest.mock import MagicMock

import pytest

import notifications.internal_monitor_notification as internal_monitor_notification
from configs import configs
from data_models.monitor_options import reaction_function_type
from models.utils.priority import AlertPriority
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


class MockNotification:
    """Mock notification class that implements BaseNotification protocol"""

    name: str
    issues_fields: list[str]
    params: dict[str, Any] = {}
    min_priority_to_send: AlertPriority = AlertPriority.informational

    @classmethod
    def create(
        cls, name: str, issues_fields: list[str], params: dict[str, Any]
    ) -> "MockNotification":
        instance = cls()
        instance.name = name
        instance.issues_fields = issues_fields
        instance.params = params
        return instance

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]:
        return []


@pytest.mark.parametrize(
    "name, issues_fields, params",
    [
        ("Monitor 1", ["id", "name", "status"], {}),
        ("Monitor 2", ["id", "name", "status"], {"param1": "value1"}),
        ("Monitor 3", ["id", "name", "status"], {"param1": "value1", "param2": "value2"}),
    ],
)
async def test_internal_monitor_notification_enabled(monkeypatch, name, issues_fields, params):
    """'internal_monitor_notification' should create notification when enabled, following the
    configs settings"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.MockNotification"
    mock_config.params = params
    monkeypatch.setattr(configs, "internal_monitors_notification", mock_config)

    get_plugin_attribute_mock = MagicMock(return_value=MockNotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    result = internal_monitor_notification.internal_monitor_notification(
        name=name, issues_fields=issues_fields
    )

    get_plugin_attribute_mock.assert_called_once_with("plugin.test.MockNotification")

    assert len(result) == 1
    assert isinstance(result[0], MockNotification)
    assert result[0].name == name
    assert result[0].issues_fields == issues_fields
    assert result[0].params == params


async def test_internal_monitor_notification_disabled(monkeypatch):
    """'internal_monitor_notification' should return empty list when internal monitors notification
    are disabled"""
    mock_config = MagicMock()
    mock_config.enabled = False
    monkeypatch.setattr(configs, "internal_monitors_notification", mock_config)

    result = internal_monitor_notification.internal_monitor_notification(
        name="Test Monitor", issues_fields=["id", "name", "status"]
    )

    assert result == []


async def test_internal_monitor_notification_invalid_notification_class(monkeypatch):
    """'internal_monitor_notification' should raise 'TypeError' if the notification class does not
    follow the 'BaseNotification' protocol"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.NotANotification"
    mock_config.params = {}
    monkeypatch.setattr(configs, "internal_monitors_notification", mock_config)

    class NotANotification:
        pass

    get_plugin_attribute_mock = MagicMock(return_value=NotANotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    expected_msg = "Attribute 'plugin.test.NotANotification' is not a valid notification"
    with pytest.raises(TypeError, match=expected_msg):
        internal_monitor_notification.internal_monitor_notification(
            name="Test Monitor", issues_fields=["id", "name", "status"]
        )

    get_plugin_attribute_mock.assert_called_once_with("plugin.test.NotANotification")


async def test_internal_monitor_notification_exception_handling(caplog, monkeypatch):
    """'internal_monitor_notification' should log an error and return an empty list if an exception
    occurs during notification creation"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.MockNotification"
    mock_config.params = {}
    monkeypatch.setattr(configs, "internal_monitors_notification", mock_config)

    monkeypatch.setattr(
        MockNotification, "create", MagicMock(side_effect=Exception("Test exception"))
    )

    get_plugin_attribute_mock = MagicMock(return_value=MockNotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    result = internal_monitor_notification.internal_monitor_notification(
        name="Test Monitor", issues_fields=["id", "name", "status"]
    )

    assert result == []
    assert_message_in_log(caplog, "Test exception")

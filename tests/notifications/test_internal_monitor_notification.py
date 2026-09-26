from typing import Any
from unittest.mock import MagicMock

import pytest

import notifications.internal_monitor_notification as internal_monitor_notification
from configs import InternalMonitorsNotificationConfig, configs
from data_models.monitor_options import reaction_function_type
from models.utils.priority import AlertPriority
from tests.test_utils import assert_message_in_log


class MockNotification:
    """Mock notification class that implements BaseNotification protocol"""

    title: str
    params: dict[str, Any] = {}
    min_priority_to_send: AlertPriority = AlertPriority.informational

    @classmethod
    def create(cls, title: str, params: dict[str, Any]) -> "MockNotification":
        instance = cls()
        instance.title = title
        instance.params = params
        return instance

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]:
        return []

    def hash(self) -> str:
        return "hash"


@pytest.mark.parametrize(
    "title, issues_fields, params",
    [
        ("Monitor 1", ["id", "name", "status"], {}),
        ("Monitor 2", ["id", "name", "status"], {"param1": "value1"}),
        ("Monitor 3", ["id", "name", "status"], {"param1": "value1", "param2": "value2"}),
    ],
)
def test_create_notification_enabled(monkeypatch, title, issues_fields, params):
    """'_create_notification' should create notification when enabled, following the configs
    settings"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.MockNotification"
    mock_config.params = params

    get_plugin_attribute_mock = MagicMock(return_value=MockNotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    result = internal_monitor_notification._create_notification(
        mock_config, title=title, issues_fields=issues_fields
    )

    get_plugin_attribute_mock.assert_called_once_with("plugin.test.MockNotification")

    assert isinstance(result, MockNotification)
    assert result.title == title
    assert result.params.pop("issues_fields") == issues_fields
    assert result.params == params


def test_create_notification_disabled():
    """'_create_notification' should return empty list when internal monitors notification are
    disabled"""
    mock_config = MagicMock()
    mock_config.enabled = False

    result = internal_monitor_notification._create_notification(
        mock_config, title="Test Monitor", issues_fields=["id", "name", "status"]
    )

    assert result is None


def test_create_notification_invalid_notification_class(monkeypatch):
    """'_create_notification' should raise 'TypeError' if the notification class does not follow
    the 'BaseNotification' protocol"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.NotANotification"
    mock_config.params = {}

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
        internal_monitor_notification._create_notification(
            mock_config, title="Test Monitor", issues_fields=["id", "name", "status"]
        )

    get_plugin_attribute_mock.assert_called_once_with("plugin.test.NotANotification")


def test_create_notification_exception_handling(monkeypatch):
    """'_create_notification' should log an error and return an None if an exception occurs during
    notification creation"""
    mock_config = MagicMock()
    mock_config.enabled = True
    mock_config.notification_class = "plugin.test.MockNotification"
    mock_config.params = {}

    monkeypatch.setattr(
        MockNotification, "create", MagicMock(side_effect=ValueError("Test exception"))
    )

    get_plugin_attribute_mock = MagicMock(return_value=MockNotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    with pytest.raises(ValueError, match="Test exception"):
        internal_monitor_notification._create_notification(
            mock_config, title="Test Monitor", issues_fields=["id", "name", "status"]
        )


@pytest.mark.parametrize(
    "notifications_configs",
    [
        [
            InternalMonitorsNotificationConfig(
                enabled=True, notification_class="mock", params={"value": "test 1"}
            ),
        ],
        [
            InternalMonitorsNotificationConfig(
                enabled=False, notification_class="mock", params={"value": "test 1"}
            ),
        ],
        [
            InternalMonitorsNotificationConfig(
                enabled=True, notification_class="mock", params={"value": "test 1"}
            ),
            InternalMonitorsNotificationConfig(
                enabled=True, notification_class="mock", params={"value": "test 2"}
            ),
        ],
        [
            InternalMonitorsNotificationConfig(
                enabled=True, notification_class="mock", params={"value": "test 1"}
            ),
            InternalMonitorsNotificationConfig(
                enabled=False, notification_class="mock", params={"value": "test 2"}
            ),
            InternalMonitorsNotificationConfig(
                enabled=False, notification_class="mock", params={"value": "test 3"}
            ),
        ],
        [
            InternalMonitorsNotificationConfig(
                enabled=False, notification_class="mock", params={"value": "test 1"}
            ),
            InternalMonitorsNotificationConfig(
                enabled=True, notification_class="mock", params={"value": "test 2"}
            ),
            InternalMonitorsNotificationConfig(
                enabled=False, notification_class="mock", params={"value": "test 3"}
            ),
        ],
    ],
)
def test_internal_monitor_notification(monkeypatch, notifications_configs):
    """'internal_monitor_notification' should create a notification for each configuration in
    'configs.internal_monitors_notifications'"""
    monkeypatch.setattr(configs, "internal_monitors_notifications", notifications_configs)

    get_plugin_attribute_mock = MagicMock(return_value=MockNotification)
    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    internal_notifications = internal_monitor_notification.internal_monitor_notification(
        "title", ["id", "value"]
    )
    notifications_params = [
        notification.params  # type:ignore[attr-defined]
        for notification in internal_notifications
    ]

    expected_notification_params = [
        {"issues_fields": ["id", "value"], **notification_config.params}
        for notification_config in notifications_configs
        if notification_config.enabled
    ]

    assert notifications_params == expected_notification_params


def test_internal_monitor_notification_error(caplog, monkeypatch):
    """'internal_monitor_notification' should log erros and not affect other notification
    configurations"""
    notifications_configs = [
        # Will trigger the 'TypeError' exception because will return a class not compatible with
        # 'BaseNotification'
        InternalMonitorsNotificationConfig(
            enabled=True, notification_class="mock.notification_1", params={"value": "test 1"}
        ),
        # Will trigger the 'ValueError' exception
        InternalMonitorsNotificationConfig(
            enabled=True, notification_class="mock.notification_2", params={"value": "test 2"}
        ),
        # Valid notification config
        InternalMonitorsNotificationConfig(
            enabled=True, notification_class="k.notification_3", params={"value": "test 3"}
        ),
    ]
    monkeypatch.setattr(configs, "internal_monitors_notifications", notifications_configs)

    # Mock the 'get_plugin_attribute' to return a invalid notification class for the first
    # notification config
    class NotANotification:
        pass

    def get_plugin_attribute_mock(notification_class_path):
        if notification_class_path == "mock.notification_1":
            return NotANotification
        return MockNotification

    monkeypatch.setattr(
        internal_monitor_notification,
        "get_plugin_attribute",
        get_plugin_attribute_mock,
    )

    # Mock MockNotification create method to raise an exception for params 'test 2'
    original_create = MockNotification.create

    def create_error_mock(title, params):
        if params["value"] == "test 2":
            raise ValueError("error with test 2")
        return original_create(title, params)

    monkeypatch.setattr(MockNotification, "create", create_error_mock)

    # Run the test
    internal_notifications = internal_monitor_notification.internal_monitor_notification(
        "title", ["id", "value"]
    )
    notifications_params = [
        notification.params  # type:ignore[attr-defined]
        for notification in internal_notifications
    ]

    assert notifications_params == [{"issues_fields": ["id", "value"], "value": "test 3"}]

    assert_message_in_log(caplog, "Attribute 'mock.notification_1' is not a valid notification")
    assert_message_in_log(caplog, "ValueError: error with test 2")

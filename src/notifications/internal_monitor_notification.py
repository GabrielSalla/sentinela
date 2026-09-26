import logging

from configs import InternalMonitorsNotificationConfig, configs
from notifications.base_notification import BaseNotification
from plugins.attribute_select import get_plugin_attribute
from utils.exception_handling import catch_exceptions

_logger = logging.getLogger("internal_monitor_notification")


def _create_notification(
    notification_config: InternalMonitorsNotificationConfig, title: str, issues_fields: list[str]
) -> BaseNotification | None:
    """Create a notification instance for internal monitors"""
    if not notification_config.enabled:
        return None

    notification_class_path = notification_config.notification_class
    notification_class = get_plugin_attribute(notification_class_path)
    params = {"issues_fields": issues_fields, **notification_config.params}

    if not isinstance(notification_class, BaseNotification):
        raise TypeError(f"Attribute {notification_class_path!r} is not a valid notification")

    return notification_class.create(title=title, params=params)


def internal_monitor_notification(title: str, issues_fields: list[str]) -> list[BaseNotification]:
    """Create a notification instance for internal monitors for each configuration in internal
    monitors notifications"""
    internal_notifications = []
    for notification_config in configs.internal_monitors_notifications:
        with catch_exceptions(_logger):
            notification = _create_notification(notification_config, title, issues_fields)
            if notification is not None:
                internal_notifications.append(notification)

    return internal_notifications

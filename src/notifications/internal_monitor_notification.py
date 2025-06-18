import logging

from configs import configs
from notifications.base_notification import BaseNotification
from plugins.attribute_select import get_plugin_attribute

_logger = logging.getLogger("internal_monitor_notification")


def internal_monitor_notification(name: str, issues_fields: list[str]) -> list[BaseNotification]:
    """Create a notification instance for internal monitors, using the settings in the configs
    file."""
    internal_monitors_notification = configs.internal_monitors_notification

    if not internal_monitors_notification.enabled:
        return []

    notification_class_path = internal_monitors_notification.notification_class
    notification_class = get_plugin_attribute(notification_class_path)
    params = internal_monitors_notification.params

    if not isinstance(notification_class, BaseNotification):
        raise TypeError(f"Attribute '{notification_class_path}' is not a valid notification")

    try:
        return [notification_class.create(name=name, issues_fields=issues_fields, params=params)]
    except Exception as e:
        _logger.error(e.args[0])
        return []

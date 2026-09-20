import logging
import os
from dataclasses import field
from functools import partial
from hashlib import md5
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from pydantic.dataclasses import dataclass

from data_models.event_payload import EventPayload
from data_models.monitor_options import reaction_function_type
from models import Alert, AlertPriority, AlertStatus, Monitor, Notification

from .. import ntfy

_logger = logging.getLogger("plugin.ntfy.notifications")

DEFAULT_SERVER_URL = "https://ntfy.sh"

NTFY_REQUEST_TIMEOUT = ClientTimeout(total=3)

DEFAULT_NOTIFY_ON_EVENTS = [
    "alert_created",
    "alert_priority_increased",
    "alert_acknowledged",
    "alert_solved",
]

# ntfy priorities run from 1 (min) to 5 (max), while alert priorities run from 1 (critical)
# to 5 (informational), so the mapping is reversed. Solved alerts use the default priority.
NTFY_PRIORITY = {
    1: 5,
    2: 4,
    3: 3,
    4: 2,
    5: 1,
    "solved": 3,
}


def _default_server_url() -> str:
    """Get the default ntfy server URL from the 'NTFY_SERVER_URL' environment variable,
    falling back to the public server"""
    return os.environ.get("NTFY_SERVER_URL") or DEFAULT_SERVER_URL


def _get_token(token_name: str) -> str:
    """Get a configured ntfy token or raise an error if it is missing"""
    token = ntfy.tokens.get(token_name.lower())
    if token is None:
        raise ValueError(
            f"Token {token_name!r} is not configured. "
            f"Set environment variable 'NTFY_TOKEN_{token_name}'"
        )
    return token


@dataclass(kw_only=True)
class NtfyNotification:
    """
    The **NtfyNotification** class manages sending notifications for alerts to an ntfy topic.
    Only the alert summary is sent (event name, priority and state), without the issues content, to
    keep the notification short. NtfyNotification objects with a different combination of `title`,
    `topic` and `min_priority_to_send` are considered different notification targets.
    - `title`: A title for the notification to help users to identify the problem.
    - `topic`: The ntfy topic where notifications will be sent.
    - `server_url`: The ntfy server URL. Uses the given value. If no value was provided, uses
    `NTFY_SERVER_URL` environment variable. If environment variable not defined, uses the default
    `https://ntfy.sh`.
    - `token_name`: Name identifying which token to use for Bearer auth. The token itself is
    read from the `NTFY_TOKEN_{token_name}` environment variable. Set to `None` for public
    topics or servers without auth. Defaults to `None`.
    - `min_priority_to_send`: Minimum alert priority that triggers a notification. Notifications
    will be sent if the alert is not acknowledged at the current priority level and it's greater
    than or equal to this setting. Defaults to `low` (P4).
    - `notify_on_events`: List of alert events that trigger a notification. Defaults to
    `alert_created`, `alert_priority_increased`, `alert_acknowledged` and `alert_solved`.
    """

    title: str
    topic: str
    server_url: str = field(default_factory=_default_server_url)
    token_name: str | None = None
    min_priority_to_send: AlertPriority = AlertPriority.low
    notify_on_events: list[str] = field(default_factory=lambda: list(DEFAULT_NOTIFY_ON_EVENTS))

    def __post_init__(self) -> None:
        """Validate notification credentials and event settings"""
        if len(self.notify_on_events) != len(set(self.notify_on_events)):
            raise ValueError("'notify_on_events' cannot contain duplicate events")

        if self.token_name is not None:
            _get_token(self.token_name)

    @classmethod
    def create(
        cls: type["NtfyNotification"],
        title: str,
        params: dict[str, Any] = {},
    ) -> "NtfyNotification":
        """Create a new instance of the 'NtfyNotification' class from the notification protocol."""
        try:
            topic = params["topic"]
        except KeyError:
            raise KeyError("Param 'topic' is not set. Unable to create 'NtfyNotification' instance")

        return cls(
            title=title,
            topic=topic,
            server_url=params.get("server_url") or _default_server_url(),
            token_name=params.get("token_name"),
            min_priority_to_send=AlertPriority[params.get("min_priority_to_send", "low")],
            notify_on_events=params.get("notify_on_events", list(DEFAULT_NOTIFY_ON_EVENTS)),
        )

    def reactions_list(self) -> list[tuple[str, list[reaction_function_type]]]:
        """Get a list of events that the notification will react to"""
        handle_notification_function = partial(handle_event, notification_options=self)
        return [
            (event_name, [handle_notification_function]) for event_name in self.notify_on_events
        ]

    def hash(self) -> str:
        """Return identifier for this notification configuration."""
        value = "|".join([self.title, self.topic, str(self.min_priority_to_send)])
        return md5(value.encode()).hexdigest()


def _get_ntfy_priority(alert: Alert) -> int:
    """Get the ntfy priority for the alert"""
    if alert.status == AlertStatus.solved:
        return NTFY_PRIORITY["solved"]
    return NTFY_PRIORITY[alert.priority]


def _build_message(alert: Alert, event_name: str) -> str:
    """Build the notification message that will be sent to the ntfy topic"""
    lines = [f"Event: {event_name}"]

    if alert.status == AlertStatus.solved:
        lines.append("Solved")
    else:
        if alert.is_priority_acknowledged:
            lines.append(f"Priority: {alert.priority} Acknowledged")
        else:
            lines.append(f"Priority: {alert.priority}")

    return "\n".join(lines)


def _build_request(
    notification_options: NtfyNotification, title: str, message: str, priority: int
) -> tuple[str, dict[str, str], str]:
    """Build the URL, headers and body of the ntfy publish request"""
    url = f"{notification_options.server_url.rstrip('/')}/{notification_options.topic}"
    headers = {
        "Title": title,
        "Priority": str(priority),
        "Markdown": "yes",
    }
    if notification_options.token_name is not None:
        token = _get_token(notification_options.token_name)
        headers["Authorization"] = f"Bearer {token}"

    return url, headers, message


async def _post_message(url: str, headers: dict[str, str], message: str) -> bool:
    """Post a message to an ntfy topic, returning 'True' if it was published"""
    try:
        async with ClientSession(timeout=NTFY_REQUEST_TIMEOUT) as session:
            async with session.post(url, headers=headers, data=message.encode("utf-8")) as response:
                return response.status == 200
    except Exception:
        return False


async def send_notification(
    monitor: Monitor,
    alert: Alert,
    notification_options: NtfyNotification,
    message: str,
) -> None:
    """Send the notification message to an ntfy topic"""
    title = f"{alert.id} - {notification_options.title}"
    priority = _get_ntfy_priority(alert)
    url, headers, body = _build_request(notification_options, title, message, priority)

    if not await _post_message(url, headers, body):
        _logger.error(
            f"Error sending ntfy message for {monitor} alert {alert.id} to topic "
            f"{notification_options.topic!r}"
        )


async def _handle_ntfy_notification(
    alert_id: int,
    notification_options: NtfyNotification,
    event_name: str,
) -> None:
    """Handle the ntfy notification for an alert"""
    alert = await Alert.get_by_id(alert_id)
    if alert is None:
        return

    notification = await Notification.get(
        Notification.monitor_id == alert.monitor_id,
        Notification.alert_id == alert.id,
        Notification.target == "ntfy",
        Notification.options_hash == notification_options.hash(),
    )

    # Only continue if the notification already exists or if the alert priority triggers a new
    # notification
    if notification is None:
        # Lower number for priority is more important, so this operation is reversed
        if alert.priority > notification_options.min_priority_to_send:
            return
        if alert.status == AlertStatus.solved:
            return

        notification = await Notification.create(
            monitor_id=alert.monitor_id,
            alert_id=alert.id,
            target="ntfy",
            options_hash=notification_options.hash(),
        )

    if alert.status == AlertStatus.solved:
        await notification.close()

    monitor = await Monitor.get_by_id(alert.monitor_id)
    # This check is just to make the typing check happy, as the monitor must exist because of the
    # alert's 'monitor_id' foreign key
    if monitor is None:
        return  # pragma: no cover

    message = _build_message(alert, event_name)

    await send_notification(
        monitor=monitor,
        alert=alert,
        notification_options=notification_options,
        message=message,
    )


async def handle_event(event: EventPayload, notification_options: NtfyNotification) -> None:
    """Handle the ntfy notification for an alert"""
    if event.event_source != "alert":
        raise ValueError(f"Invalid event source {event.event_source!r}")

    await _handle_ntfy_notification(event.event_source_id, notification_options, event.event_name)

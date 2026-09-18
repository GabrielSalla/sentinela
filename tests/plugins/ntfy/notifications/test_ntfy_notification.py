from typing import Any
from unittest.mock import AsyncMock

import pytest

import plugins.ntfy.notifications.ntfy_notification as ntfy_notification
import utils.time as time_utils
from data_models.event_payload import EventPayload
from models import (
    Alert,
    AlertPriority,
    AlertStatus,
    Monitor,
    Notification,
    NotificationStatus,
)
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(scope="function")
def mock_post_message(monkeypatch):
    """Mock the ntfy HTTP post, avoiding any real network call"""
    mock = AsyncMock(return_value=True)
    monkeypatch.setattr(ntfy_notification, "_post_message", mock)
    return mock


def _make_fake_session(
    status: int = 200,
    error: Exception | None = None,
    calls: list[dict[str, Any]] | None = None,
) -> Any:
    """Build a fake aiohttp ClientSession class"""

    class FakeResponse:
        status: int

        def __init__(self) -> None:
            self.status = status

        async def __aenter__(self) -> "FakeResponse":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

    class FakeSession:
        def __init__(self, *args: Any, **kwargs: Any): ...

        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *args: Any) -> bool:
            return False

        def post(
            self,
            url: str,
            headers: dict[str, str] | None = None,
            data: bytes | None = None,
        ) -> FakeResponse:
            if calls is not None:
                calls.append({"url": url, "headers": headers, "data": data})
            if error is not None:
                raise error
            return FakeResponse()

    return FakeSession


@pytest.mark.parametrize(
    "params",
    [
        {"topic": "my-topic"},
        {"topic": "my-topic", "server_url": "https://ntfy.example.com", "token_name": "myapp"},
        {"topic": "my-topic", "min_priority_to_send": "moderate"},
        {
            "topic": "my-topic",
            "server_url": "https://ntfy.example.com",
            "token_name": "myapp",
            "min_priority_to_send": "critical",
        },
        {
            "topic": "my-topic",
            "notify_on_events": ["alert_created", "alert_solved"],
        },
    ],
)
async def test_ntfynotification_create(monkeypatch, params):
    """'NtfyNotification.create' should create an instance with correct default values and
    properly apply custom parameters"""
    monkeypatch.delenv("NTFY_SERVER_URL", raising=False)
    monkeypatch.setattr(ntfy_notification.ntfy, "tokens", {"myapp": "tk_123"})
    result = ntfy_notification.NtfyNotification.create(title="Test Monitor", params=params)

    assert isinstance(result, ntfy_notification.NtfyNotification)
    assert result.title == "Test Monitor"
    assert result.topic == params["topic"]
    assert result.server_url == params.get("server_url", ntfy_notification.DEFAULT_SERVER_URL)
    assert result.token_name == params.get("token_name")

    if "min_priority_to_send" in params:
        assert result.min_priority_to_send == AlertPriority[params["min_priority_to_send"]]
    else:
        assert result.min_priority_to_send == AlertPriority.low

    assert result.notify_on_events == params.get(
        "notify_on_events", ntfy_notification.DEFAULT_NOTIFY_ON_EVENTS
    )


@pytest.mark.parametrize(
    "params, expected_server_url",
    [
        ({"topic": "my-topic"}, "https://ntfy.example.com"),
        (
            {"topic": "my-topic", "server_url": "https://ntfy.other.com"},
            "https://ntfy.other.com",
        ),
    ],
)
async def test_ntfynotification_create_server_url_env(monkeypatch, params, expected_server_url):
    """'NtfyNotification.create' should use 'NTFY_SERVER_URL' when 'server_url' is not set,
    and prefer an explicit 'server_url' over it"""
    monkeypatch.setenv("NTFY_SERVER_URL", "https://ntfy.example.com")
    result = ntfy_notification.NtfyNotification.create(title="Test Monitor", params=params)

    assert result.server_url == expected_server_url


async def test_ntfynotification_default_server_url_env(monkeypatch):
    """'NtfyNotification' should use 'NTFY_SERVER_URL' as default 'server_url', falling back
    to the public server when it is not set"""
    monkeypatch.setenv("NTFY_SERVER_URL", "https://ntfy.example.com")
    result = ntfy_notification.NtfyNotification(title="Test Monitor", topic="my-topic")
    assert result.server_url == "https://ntfy.example.com"

    monkeypatch.delenv("NTFY_SERVER_URL")
    result = ntfy_notification.NtfyNotification(title="Test Monitor", topic="my-topic")
    assert result.server_url == ntfy_notification.DEFAULT_SERVER_URL


async def test_ntfynotification_create_without_topic():
    """'NtfyNotification.create' should raise KeyError if the 'topic' param is not set"""
    expected_error = "Param 'topic' is not set. Unable to create 'NtfyNotification' instance"
    with pytest.raises(KeyError, match=expected_error):
        ntfy_notification.NtfyNotification.create(title="Test", params={})


async def test_ntfynotification_create_without_token(monkeypatch):
    """'NtfyNotification.create' should raise if the configured token is missing"""
    monkeypatch.setattr(ntfy_notification.ntfy, "tokens", {})

    with pytest.raises(ValueError, match="Token 'myapp' is not configured"):
        ntfy_notification.NtfyNotification.create(
            title="Test",
            params={"topic": "my-topic", "token_name": "myapp"},
        )


async def test_ntfynotification_duplicate_notify_on_events():
    """'NtfyNotification' should reject duplicate notification events"""
    with pytest.raises(ValueError, match="cannot contain duplicate events"):
        ntfy_notification.NtfyNotification(
            title="title",
            topic="topic",
            notify_on_events=["alert_created", "alert_created"],
        )


@pytest.mark.parametrize(
    "notify_on_events",
    [
        ["alert_created", "alert_priority_increased", "alert_acknowledged", "alert_solved"],
        [],
        ["alert_created"],
        ["alert_solved", "alert_created"],
        ["alert_updated", "alert_priority_decreased", "alert_locked"],
    ],
)
async def test_ntfynotification_reactions_list(notify_on_events):
    """'NtfyNotification.reactions_list' should react only to the listed alert events"""
    notification_options = ntfy_notification.NtfyNotification(
        title="title",
        topic="topic",
        notify_on_events=notify_on_events,
    )

    reactions_list = notification_options.reactions_list()
    events_names = [reaction[0] for reaction in reactions_list]
    assert events_names == notify_on_events


async def test_ntfynotification_reactions_list_default():
    """'NtfyNotification.reactions_list' should react to all four events by default"""
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    reactions_list = notification_options.reactions_list()
    events_names = {reaction[0] for reaction in reactions_list}
    assert events_names == set(ntfy_notification.DEFAULT_NOTIFY_ON_EVENTS)


async def test_ntfynotification_hash():
    """'NtfyNotification.hash' should identify notification options"""
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")
    same_options = ntfy_notification.NtfyNotification(title="title", topic="topic")
    different_options = ntfy_notification.NtfyNotification(title="title", topic="other-topic")

    assert notification_options.hash() == same_options.hash()
    assert notification_options.hash() != different_options.hash()


@pytest.mark.parametrize(
    "status, priority, expected_result",
    [
        (AlertStatus.active, 1, 5),
        (AlertStatus.active, 2, 4),
        (AlertStatus.active, 3, 3),
        (AlertStatus.active, 4, 2),
        (AlertStatus.active, 5, 1),
        (AlertStatus.solved, 1, 3),
        (AlertStatus.solved, 5, 3),
    ],
)
async def test_get_ntfy_priority(sample_monitor: Monitor, status, priority, expected_result):
    """'_get_ntfy_priority' should map the alert priority to the reversed ntfy priority"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=status,
        priority=priority,
    )

    assert ntfy_notification._get_ntfy_priority(alert) == expected_result


@pytest.mark.parametrize(
    "acknowledged, acknowledge_priority, expected_priority",
    [
        (False, None, "Priority: 2"),
        (True, 3, "Priority: 2"),
        (True, 2, "Priority: 2 Acknowledged"),
    ],
)
async def test_build_message(
    sample_monitor: Monitor, acknowledged, acknowledge_priority, expected_priority
):
    """'_build_message' should join the event name and the alert priority"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=acknowledged,
        priority=2,
        acknowledge_priority=acknowledge_priority,
    )

    result = ntfy_notification._build_message(alert, "alert_created")

    assert result == f"Event: alert_created\n{expected_priority}"


async def test_build_message_solved(sample_monitor: Monitor):
    """'_build_message' should include the event name and the solved state for solved alerts"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id, status=AlertStatus.solved, solved_at=time_utils.now()
    )

    result = ntfy_notification._build_message(alert, "alert_solved")

    assert result == "Event: alert_solved\nSolved"


@pytest.mark.parametrize(
    "token_name, tokens, expected_authorization",
    [
        (None, {}, None),
        ("myapp", {"myapp": "tk_123"}, "Bearer tk_123"),
    ],
)
async def test_build_request(monkeypatch, token_name, tokens, expected_authorization):
    """'_build_request' should build the publish URL, headers and body, reading the token from
    the loaded 'tokens'"""
    monkeypatch.setattr("plugins.ntfy.ntfy.tokens", tokens)
    notification_options = ntfy_notification.NtfyNotification(
        title="title",
        topic="my-topic",
        server_url="https://ntfy.example.com/",
        token_name=token_name,
    )

    url, headers, body = ntfy_notification._build_request(
        notification_options, "1 - title", "message", 4
    )

    assert url == "https://ntfy.example.com/my-topic"
    assert headers["Title"] == "1 - title"
    assert headers["Priority"] == "4"
    assert body == "message"
    if expected_authorization is None:
        assert "Authorization" not in headers
    else:
        assert headers["Authorization"] == expected_authorization


async def test_build_request_missing_token(monkeypatch):
    """'_build_request' should raise if a configured token is no longer available"""
    tokens = {"myapp": "tk_123"}
    monkeypatch.setattr(ntfy_notification.ntfy, "tokens", tokens)
    notification_options = ntfy_notification.NtfyNotification(
        title="title",
        topic="my-topic",
        token_name="myapp",
    )
    tokens.clear()

    with pytest.raises(ValueError, match="Token 'myapp' is not configured"):
        ntfy_notification._build_request(notification_options, "title", "message", 4)


@pytest.mark.parametrize("status_code, expected_result", [(200, True), (400, False), (500, False)])
async def test_post_message(monkeypatch, status_code, expected_result):
    """'_post_message' should return 'True' only when ntfy answers with status 200"""
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        ntfy_notification, "ClientSession", _make_fake_session(status=status_code, calls=calls)
    )

    result = await ntfy_notification._post_message(
        "https://ntfy.sh/topic", {"Title": "title"}, "message"
    )

    assert result == expected_result
    assert calls[0]["url"] == "https://ntfy.sh/topic"
    assert calls[0]["data"] == "message".encode("utf-8")


async def test_post_message_error(monkeypatch):
    """'_post_message' should return 'False' when the request raises an exception"""
    monkeypatch.setattr(
        ntfy_notification,
        "ClientSession",
        _make_fake_session(error=ConnectionError("no network")),
    )

    result = await ntfy_notification._post_message("https://ntfy.sh/topic", {"Title": "t"}, "m")

    assert result is False


async def test_send_notification(mock_post_message, sample_monitor: Monitor):
    """'send_notification' should post the message with the alert title and ntfy priority"""
    alert = await Alert.create(monitor_id=sample_monitor.id, priority=2)
    notification_options = ntfy_notification.NtfyNotification(
        title="Alert name",
        topic="my-topic",
        server_url="https://ntfy.sh",
    )

    await ntfy_notification.send_notification(
        monitor=sample_monitor,
        alert=alert,
        notification_options=notification_options,
        message="message",
    )

    mock_post_message.assert_awaited_once()
    url, headers, body = mock_post_message.call_args[0]
    assert url == "https://ntfy.sh/my-topic"
    assert headers["Title"] == f"{alert.id} - Alert name"
    assert headers["Priority"] == "4"
    assert body == "message"


async def test_send_notification_error(caplog, mock_post_message, sample_monitor: Monitor):
    """'send_notification' should log an error when the post fails"""
    mock_post_message.return_value = False
    alert = await Alert.create(monitor_id=sample_monitor.id)
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="my-topic")

    await ntfy_notification.send_notification(
        monitor=sample_monitor,
        alert=alert,
        notification_options=notification_options,
        message="message",
    )

    assert_message_in_log(caplog, "Error sending ntfy message")


async def test_handle_ntfy_notification_no_alert(mock_post_message):
    """'_handle_ntfy_notification' should just return if the alert doesn't exist"""
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    await ntfy_notification._handle_ntfy_notification(
        alert_id=99999999,
        notification_options=notification_options,
        event_name="alert_created",
    )

    mock_post_message.assert_not_called()


async def test_handle_ntfy_notification_min_priority_to_send(
    mock_post_message, sample_monitor: Monitor
):
    """'_handle_ntfy_notification' should just return if the alert priority is lower than
    'min_priority_to_send' and there's no notification yet"""
    alert = await Alert.create(monitor_id=sample_monitor.id, priority=4)
    notification_options = ntfy_notification.NtfyNotification(
        title="title",
        topic="topic",
        min_priority_to_send=AlertPriority.moderate,
    )

    await ntfy_notification._handle_ntfy_notification(
        alert_id=alert.id,
        notification_options=notification_options,
        event_name="alert_created",
    )

    mock_post_message.assert_not_called()
    assert await Notification.get(Notification.alert_id == alert.id) is None


async def test_handle_ntfy_notification_no_notification_alert_solved(
    mock_post_message, sample_monitor: Monitor
):
    """'_handle_ntfy_notification' should not create a notification if the alert is solved"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
        priority=2,
        solved_at=time_utils.now(),
    )
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    await ntfy_notification._handle_ntfy_notification(
        alert_id=alert.id,
        notification_options=notification_options,
        event_name="alert_solved",
    )

    mock_post_message.assert_not_called()
    assert await Notification.get(Notification.alert_id == alert.id) is None


async def test_handle_ntfy_notification_first_send(mock_post_message, sample_monitor: Monitor):
    """'_handle_ntfy_notification' should create the notification and send the message"""
    alert = await Alert.create(monitor_id=sample_monitor.id, priority=2)
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    await ntfy_notification._handle_ntfy_notification(
        alert_id=alert.id,
        notification_options=notification_options,
        event_name="alert_created",
    )

    mock_post_message.assert_awaited_once()
    notification = await Notification.get(Notification.alert_id == alert.id)
    assert notification is not None
    assert notification.target == "ntfy"
    assert notification.options_hash == notification_options.hash()
    assert notification.status == NotificationStatus.active


async def test_handle_ntfy_notification_existing_resends(
    mock_post_message, sample_monitor: Monitor
):
    """'_handle_ntfy_notification' should send again even if the notification already exists,
    as ntfy messages can't be updated"""
    alert = await Alert.create(monitor_id=sample_monitor.id, priority=4)
    notification_options = ntfy_notification.NtfyNotification(
        title="title",
        topic="topic",
        min_priority_to_send=AlertPriority.moderate,
    )
    await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="ntfy",
        options_hash=notification_options.hash(),
        data={"sent": True},
    )

    await ntfy_notification._handle_ntfy_notification(
        alert_id=alert.id,
        notification_options=notification_options,
        event_name="alert_acknowledged",
    )

    mock_post_message.assert_awaited_once()


async def test_handle_ntfy_notification_alert_solved(mock_post_message, sample_monitor: Monitor):
    """'_handle_ntfy_notification' should close the notification and send the solved message"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
        priority=2,
        solved_at=time_utils.now(),
    )
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")
    notification = await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="ntfy",
        options_hash=notification_options.hash(),
    )

    await ntfy_notification._handle_ntfy_notification(
        alert_id=alert.id,
        notification_options=notification_options,
        event_name="alert_solved",
    )

    mock_post_message.assert_awaited_once()
    await notification.refresh()
    assert notification.status == NotificationStatus.closed


async def test_handle_ntfy_notification_multiple_options(
    mock_post_message, sample_monitor: Monitor
):
    """'_handle_ntfy_notification' should create one notification per option set"""
    alert = await Alert.create(monitor_id=sample_monitor.id, priority=2)
    notification_options = [
        ntfy_notification.NtfyNotification(title="title", topic="topic-1"),
        ntfy_notification.NtfyNotification(title="title", topic="topic-2"),
    ]

    for options in notification_options:
        await ntfy_notification._handle_ntfy_notification(
            alert_id=alert.id,
            notification_options=options,
            event_name="alert_created",
        )

    assert mock_post_message.await_count == 2
    notifications = await Notification.get_all(Notification.alert_id == alert.id)
    assert len(notifications) == 2
    assert {notification.options_hash for notification in notifications} == {
        options.hash() for options in notification_options
    }


@pytest.mark.parametrize("alert_id", [1, 10, 123])
async def test_handle_event(monkeypatch, alert_id):
    """'handle_event' should call '_handle_ntfy_notification' with the alert id, the
    notification options and the event name"""
    handle_mock = AsyncMock()
    monkeypatch.setattr(ntfy_notification, "_handle_ntfy_notification", handle_mock)

    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    await ntfy_notification.handle_event(
        EventPayload(
            event_source="alert",
            event_source_id=alert_id,
            event_source_monitor_id=0,
            event_name="alert_created",
            event_data={},
            extra_payload=None,
        ),
        notification_options,
    )

    handle_mock.assert_awaited_once_with(alert_id, notification_options, "alert_created")


@pytest.mark.parametrize("event_source", ["monitor", "issue", "other"])
async def test_handle_event_invalid_event_source(event_source):
    """'handle_event' should raise 'ValueError' if the event source is not 'alert'"""
    notification_options = ntfy_notification.NtfyNotification(title="title", topic="topic")

    with pytest.raises(ValueError, match=f"Invalid event source {event_source!r}"):
        await ntfy_notification.handle_event(
            EventPayload(
                event_source=event_source,
                event_source_id=1,
                event_source_monitor_id=0,
                event_name="",
                event_data={},
                extra_payload=None,
            ),
            notification_options,
        )

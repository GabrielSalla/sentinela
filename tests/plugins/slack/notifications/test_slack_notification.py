from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from slack_sdk.web.async_client import AsyncSlackResponse

import plugins.slack.notifications.slack_notification as slack_notification
import plugins.slack.slack as slack
import utils.time as time_utils
from configs import configs
from data_models.event_payload import EventPayload
from models import (
    Alert,
    AlertPriority,
    AlertStatus,
    Issue,
    IssueStatus,
    Monitor,
    Notification,
    NotificationStatus,
)
from tests.test_utils import assert_message_in_log

from .. import slack_mock

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "channel, mention, name, issues_fields, params",
    [
        (
            "C1234567890",
            "U1234567890",
            "Test Monitor",
            ["id", "name", "value"],
            {},
        ),
        (
            "C0987654321",
            "U0987654321",
            "Another Monitor",
            ["other_id", "other_value"],
            {},
        ),
        (
            "C1234567890",
            "U1234567890",
            "Priority to send test",
            ["id"],
            {"min_priority_to_send": "moderate"},
        ),
        (
            "C1234567890",
            "U1234567890",
            "Mention on update test",
            ["id"],
            {"mention_on_update": True},
        ),
        (
            "C1234567890",
            "U1234567890",
            "Priority to mention test",
            ["id"],
            {"min_priority_to_mention": "high"},
        ),
        (
            "C1234567890",
            "U1234567890",
            "Issue show limit test",
            ["id"],
            {"issue_show_limit": 25},
        ),
        (
            "C1234567890",
            "U1234567890",
            "All parameters test",
            ["id"],
            {
                "min_priority_to_send": "critical",
                "min_priority_to_mention": "high",
                "mention_on_update": True,
                "issue_show_limit": 5,
            },
        ),
    ],
)
async def test_slacknotification_create(monkeypatch, channel, mention, name, issues_fields, params):
    """'SlackNotification.create' should create a SlackNotification instance with correct
    default values and properly apply custom parameters"""
    # Set up environment variables that the create method expects
    monkeypatch.setenv("SLACK_MAIN_CHANNEL", channel)
    monkeypatch.setenv("SLACK_MAIN_MENTION", mention)

    result = slack_notification.SlackNotification.create(
        name=name,
        issues_fields=issues_fields,
        params=params,
    )

    assert isinstance(result, slack_notification.SlackNotification)

    assert result.channel == channel
    assert result.title == name
    assert result.issues_fields == issues_fields

    if "min_priority_to_send" in params:
        assert result.min_priority_to_send == AlertPriority[params["min_priority_to_send"]]
    else:
        assert result.min_priority_to_send == AlertPriority.low

    if "mention_on_update" in params:
        assert result.mention_on_update == params["mention_on_update"]
    else:
        assert not result.mention_on_update

    if "min_priority_to_mention" in params:
        assert result.min_priority_to_mention == AlertPriority[params["min_priority_to_mention"]]
    else:
        assert result.min_priority_to_mention == AlertPriority.moderate

    if "issue_show_limit" in params:
        assert result.issue_show_limit == params["issue_show_limit"]
    else:
        assert result.issue_show_limit == 10


async def test_slacknotification_create_without_channel(monkeypatch):
    """'SlackNotification.create' should raise KeyError if the SLACK_MAIN_CHANNEL environment
    variable is not set"""
    monkeypatch.delenv("SLACK_MAIN_CHANNEL", raising=False)

    expected_error = (
        "Environment variable 'SLACK_MAIN_CHANNEL' is not set. "
        "Unable to create 'SlackNotification' instance"
    )
    with pytest.raises(KeyError, match=expected_error):
        slack_notification.SlackNotification.create(name="Test", issues_fields=["id"])


async def test_slacknotification_reactions_list():
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
    )

    reactions_list = notification_options.reactions_list()
    events_names = {reaction[0] for reaction in reactions_list}
    expected_events_names = {
        "alert_acknowledge_dismissed",
        "alert_acknowledged",
        "alert_locked",
        "alert_solved",
        "alert_unlocked",
        "alert_updated",
    }
    assert events_names == expected_events_names


@pytest.mark.parametrize(
    "priority, acknowledge_priority, expected_result",
    [
        (1, 2, "Priority: 1"),
        (1, 1, "Priority: 1 (1)"),
        (2, 3, "Priority: 2"),
        (2, 2, "Priority: 2 (2)"),
        (1, 3, "Priority: 1"),
        (3, 1, "Priority: 3 (1)"),
    ],
)
async def test_alert_priority_info(
    sample_monitor: Monitor, priority, acknowledge_priority, expected_result
):
    """'_alert_priority_info' should return the priority information for the alert"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
        priority=priority,
        acknowledge_priority=acknowledge_priority,
    )

    result = slack_notification._alert_priority_info(alert)
    assert result == expected_result


@pytest.mark.parametrize("number", range(5))
async def test_issue_count_info(sample_monitor: Monitor, number):
    """'_issue_count_info' should return the issues number information for the alert"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )

    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(2 * number)
        ]
    )
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(10 + i),
                data={"id": 10 + i},
                status=IssueStatus.solved,
                alert_id=alert.id,
            )
            for i in range(number)
        ]
    )

    result = await slack_notification._issue_count_info(alert)
    assert result == f"Issues: {2 * number}"


@pytest.mark.parametrize(
    "status, locked, priority, acknowledge_priority, expected_result",
    [
        (AlertStatus.solved, True, 3, 1, None),
        (AlertStatus.active, True, 3, 1, "*Locked*"),
        (AlertStatus.active, True, 1, 3, "*Locked*"),
        (AlertStatus.active, False, 3, 1, "*Acknowledged*"),
        (AlertStatus.active, False, 1, 3, None),
    ],
)
async def test_alert_state_info(
    sample_monitor: Monitor, status, locked, priority, acknowledge_priority, expected_result
):
    """'_alert_state_info' should return the alert state"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=status,
        acknowledged=True,
        locked=locked,
        priority=priority,
        acknowledge_priority=acknowledge_priority,
    )

    result = slack_notification._alert_state_info(alert)
    assert result == expected_result


@pytest.mark.parametrize(
    "status, locked, priority, acknowledge_priority, expected_result",
    [
        (AlertStatus.solved, True, 3, 1, []),
        (AlertStatus.active, True, 3, 1, ["Priority: 3 (1)", "Issues: 5", "*Locked*"]),
        (AlertStatus.active, True, 1, 2, ["Priority: 1", "Issues: 5", "*Locked*"]),
        (AlertStatus.active, False, 4, 2, ["Priority: 4 (2)", "Issues: 5", "*Acknowledged*"]),
        (AlertStatus.active, False, 3, 5, ["Priority: 3", "Issues: 5"]),
    ],
)
async def test_build_notification_status(
    sample_monitor: Monitor, status, locked, priority, acknowledge_priority, expected_result
):
    """'_build_notification_status' should build the status part for the notification message"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=status,
        acknowledged=True,
        locked=locked,
        priority=priority,
        acknowledge_priority=acknowledge_priority,
    )
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={"id": i},
                alert_id=alert.id,
            )
            for i in range(5)
        ]
    )

    result = await slack_notification._build_notification_status(sample_monitor, alert, None)
    assert result == expected_result


@pytest.mark.parametrize(
    "status, created_at, solved_at, timezone, expected_result",
    [
        (
            AlertStatus.active,
            datetime(2024, 1, 2, 12, 34, 56, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 12, 56, 34, tzinfo=timezone.utc),
            "utc",
            ["Triggered at: `2024-01-02 12:34:56`"],
        ),
        (
            AlertStatus.active,
            datetime(2022, 3, 6, 11, 22, 33, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 11, 33, 44, tzinfo=timezone.utc),
            "America/Sao_Paulo",
            ["Triggered at: `2022-03-06 08:22:33`"],
        ),
        (
            AlertStatus.solved,
            datetime(2024, 1, 2, 12, 34, 56, tzinfo=timezone.utc),
            datetime(2024, 1, 2, 12, 56, 34, tzinfo=timezone.utc),
            "utc",
            ["Triggered at: `2024-01-02 12:34:56`", "Solved at: `2024-01-02 12:56:34`"],
        ),
        (
            AlertStatus.solved,
            datetime(2022, 3, 6, 1, 22, 33, tzinfo=timezone.utc),
            datetime(2023, 10, 30, 22, 33, 44, tzinfo=timezone.utc),
            "America/Sao_Paulo",
            ["Triggered at: `2022-03-05 22:22:33`", "Solved at: `2023-10-30 19:33:44`"],
        ),
    ],
)
async def test_build_notification_timestamps(
    monkeypatch, sample_monitor: Monitor, status, created_at, solved_at, timezone, expected_result
):
    """'_build_notification_timestamps' should build the timestamps information for the
    notification message"""
    monkeypatch.setattr(configs, "time_zone", timezone)
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=status,
        created_at=created_at,
        solved_at=solved_at,
    )

    result = await slack_notification._build_notification_timestamps(sample_monitor, alert, None)
    assert result == expected_result


@pytest.mark.parametrize(
    "status, issues_fields, issues_number",
    [
        (AlertStatus.solved, ["id", "value", "something_else"], 1),
        (AlertStatus.active, ["id", "value", "something_else"], 5),
        (AlertStatus.active, ["id", "value", "something_else"], 10),
        (AlertStatus.active, ["id", "value", "something_else"], 15),
        (AlertStatus.active, ["id", "something_else"], 3),
        (AlertStatus.active, ["id", "value"], 8),
        (AlertStatus.active, ["value", "something_else"], 12),
    ],
)
async def test_build_issues_table(sample_monitor: Monitor, status, issues_fields, issues_number):
    """'_build_issues_table' should return the content of the message for the notification
    message"""
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=issues_fields,
        issue_show_limit=10,
    )

    alert = await Alert.create(monitor_id=sample_monitor.id, status=status)

    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(i),
                data={
                    "id": i,
                    "value": i + 10,
                    "something_else": i * 11,
                },
                alert_id=alert.id,
            )
            for i in range(issues_number)
        ]
    )
    await Issue.create_batch(
        [
            Issue(
                monitor_id=sample_monitor.id,
                model_id=str(100 + i),
                data={"id": 100 + i},
                status=IssueStatus.solved,
                alert_id=alert.id,
            )
            for i in range(2)
        ]
    )

    result = await slack_notification._build_issues_table(
        sample_monitor, alert, notification_options
    )

    if status == AlertStatus.solved:
        assert result is None
        return

    assert result is not None

    for column in ["id", "value", "something_else"]:
        if column in issues_fields:
            assert column in result
        else:
            assert column not in result

    if issues_number > 10:
        assert len(result.split("\n")) == 15
        assert f"\n{issues_number - 10} more..." in result
    else:
        assert len(result.split("\n")) == issues_number + 4
        assert "more..." not in result


@pytest.mark.parametrize("slack_websocket_enabled", [False, True])
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("acknowledge_priority", [1, 2, 3])
@pytest.mark.parametrize("solvable", [False, True])
async def test_build_notification_buttons(
    monkeypatch,
    sample_monitor: Monitor,
    slack_websocket_enabled,
    locked,
    acknowledge_priority,
    solvable,
):
    """'_build_notification_buttons' should return the list with the correct buttons according to
    the alert parameters and the monitor's issue options. If the slack websocket is disabled, it
    should return an empty list"""
    monkeypatch.setenv("SLACK_WEBSOCKET_ENABLED", str(slack_websocket_enabled).lower())
    monkeypatch.setattr(sample_monitor.code.issue_options, "solvable", solvable)
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        acknowledged=True,
        locked=locked,
        priority=2,
        acknowledge_priority=acknowledge_priority,
    )

    result = await slack_notification._build_notification_buttons(sample_monitor, alert, None)

    if not slack_websocket_enabled:
        assert len(result) == 0
        return

    # Assert the buttons attributes and their order in the list
    index = 0
    if acknowledge_priority > 2:
        button = result[index]
        assert button.text == "Ack"
        assert button.action_id == f"sentinela_ack_{alert.id}"
        assert button.value == f"ack {alert.id}"
        index += 1

    if not locked:
        button = result[index]
        assert button.text == "Lock"
        assert button.action_id == f"sentinela_lock_{alert.id}"
        assert button.value == f"lock {alert.id}"
        index += 1

    if not solvable:
        button = result[index]
        assert button.text == "Solve"
        assert button.action_id == f"sentinela_solve_{alert.id}"
        assert button.value == f"solve {alert.id}"
        index += 1


async def test_build_notification_buttons_solved(monkeypatch, sample_monitor: Monitor):
    """'_build_notification_buttons' should return an empty list if the alert is solved"""
    monkeypatch.setenv("SLACK_WEBSOCKET_ENABLED", "true")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
    )

    result = await slack_notification._build_notification_buttons(sample_monitor, alert, None)

    assert result == []


async def test_get_attachment_color_solved(sample_monitor: Monitor):
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
    )
    result = slack_notification._get_attachment_color(alert)
    assert result == slack_notification.PRIORITY_COLOR["solved"]


@pytest.mark.parametrize("priority", range(1, 6))
async def test_get_attachment_color_not_solved(sample_monitor: Monitor, priority):
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=priority,
    )
    result = slack_notification._get_attachment_color(alert)
    assert result == slack_notification.PRIORITY_COLOR[priority]


@pytest.mark.parametrize("alert_status", [AlertStatus.active, AlertStatus.solved])
@pytest.mark.parametrize("locked", [False, True])
@pytest.mark.parametrize("priority", range(1, 4))
@pytest.mark.parametrize("acknowledge_priority", range(1, 4))
async def test_build_attachments(
    mocker, sample_monitor: Monitor, alert_status, locked, priority, acknowledge_priority
):
    """'_build_attachments' should build the notification message attachments with the message
    blocks, attachment color and fallback message, while filtering empty/None message blocks"""
    slack_build_attachments_spy: MagicMock = mocker.spy(slack, "build_attachments")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
        acknowledged=True,
        locked=locked,
        priority=priority,
        acknowledge_priority=acknowledge_priority,
        solved_at=time_utils.now(),
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )

    await slack_notification._build_attachments(sample_monitor, alert, notification_options)

    slack_build_attachments_spy.assert_called_once()
    call_args = slack_build_attachments_spy.call_args

    # Assert there are no 'None' or '[]' blocks
    assert all([block for block in call_args[0]])
    assert call_args[1]["attachment_color"] is not None
    assert call_args[1]["fallback"] is not None


async def test_send_notification(mocker, monkeypatch, sample_monitor: Monitor):
    """'send_notification' should send a message to the channel and store the message timestamp to
    the notification data"""
    monkeypatch.setattr(slack_mock, "response_ts", "123456789")
    slack_send_spy: MagicMock = mocker.spy(slack, "send")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
    )

    await slack_notification.send_notification(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        attachments=[],
    )

    slack_send_spy.assert_called_once_with(channel="channel", attachments=[])

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "123456789"}


async def test_send_notification_error(caplog, monkeypatch, sample_monitor: Monitor):
    """'send_notification' should send a message to the channel and log an error if it fails"""
    monkeypatch.setattr(slack_mock, "error", "send_error")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
    )

    await slack_notification.send_notification(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        attachments=[],
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data is None
    assert_message_in_log(caplog, "Error sending slack message")


async def test_update_notification(mocker, sample_monitor: Monitor):
    """'update_notification' should update a message in the channel"""
    slack_update_spy: MagicMock = mocker.spy(slack, "update")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "1111"},
    )

    await slack_notification.update_notification(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        attachments=[],
    )

    slack_update_spy.assert_called_once_with(channel="channel", ts="1111", attachments=[])

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "1111"}


@pytest.mark.parametrize("update_error", slack_notification.RESEND_ERRORS)
async def test_update_notification_error_resend(
    caplog, monkeypatch, sample_monitor: Monitor, update_error
):
    """'update_notification' should update a message in the channel and if it fails, try to send
    it again, updating the timestamp in the notification data"""
    monkeypatch.setattr(slack_mock, "response_ts", "999")
    update_response = AsyncMock(
        return_value=AsyncSlackResponse(
            client=None,
            http_verb="",
            api_url="",
            req_args={},
            data={"ok": False, "error": update_error},
            headers={},
            status_code=200,
        )
    )
    monkeypatch.setattr(slack, "update", update_response)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "1111", "mention_ts": "123"},
    )

    await slack_notification.update_notification(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        attachments=[],
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "999", "mention_ts": None}
    assert_message_in_log(caplog, "Unable to update message for")
    assert_message_in_log(caplog, "resending")


@pytest.mark.parametrize("update_error", ["other_error", "no_resend"])
async def test_update_notification_error_no_resend(
    caplog, monkeypatch, sample_monitor: Monitor, update_error
):
    """'update_notification' should update a message in the channel and if it fails and if the
    error doesn't indicate that the message should be sent again, it should log an error"""
    monkeypatch.setattr(slack_mock, "response_ts", "123")
    update_response = AsyncMock(
        return_value=AsyncSlackResponse(
            client=None,
            http_verb="",
            api_url="",
            req_args={},
            data={"ok": False, "error": update_error},
            headers={},
            status_code=200,
        )
    )
    monkeypatch.setattr(slack, "update", update_response)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "22"},
    )

    await slack_notification.update_notification(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        attachments=[],
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "22"}
    assert_message_in_log(caplog, "Error updating slack message for")


async def test_delete_notification(mocker, sample_monitor: Monitor):
    """'_delete_notification' should delete a message in the channel and clear the notification
    information from the notification data"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33", "mention_ts": "123"},
    )

    await slack_notification._delete_notification(notification=notification)

    slack_delete_spy.assert_called_once_with(channel="channel", ts="33")

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {
        "channel": None,
        "ts": None,
        "mention_ts": "123",
    }


async def test_delete_notification_no_ts(mocker, sample_monitor: Monitor):
    """'_delete_notification' should just clear the notification information from the notification
    data if the notification doesn't have a timestamp"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel"},
    )

    await slack_notification._delete_notification(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": None, "ts": None}


async def test_delete_notification_none_ts(mocker, sample_monitor: Monitor):
    """'_delete_notification' should just clear the notification information from the notification
    data if the notification have 'None' as the message timestamp"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": None},
    )

    await slack_notification._delete_notification(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": None, "ts": None}


async def test_delete_notification_no_channel(mocker, sample_monitor: Monitor):
    """'_delete_notification' should just clear the notification information from the notification
    data if the notification doesn't have a channel"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"ts": "33"},
    )

    await slack_notification._delete_notification(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": None, "ts": None}


async def test_delete_notification_none_channel(mocker, sample_monitor: Monitor):
    """'_delete_notification' should just clear the notification information from the notification
    data if the notification have 'None' as the channel"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": None, "ts": "33"},
    )

    await slack_notification._delete_notification(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": None, "ts": None}


async def test_delete_notification_error(monkeypatch, sample_monitor: Monitor):
    """'_delete_notification' should delete a message in the channel even if there's an error and
    clear the notification information from the notification data"""
    delete_response = AsyncMock(
        return_value=AsyncSlackResponse(
            client=None,
            http_verb="",
            api_url="",
            req_args={},
            data={"ok": False, "error": "delete_error"},
            headers={},
            status_code=200,
        )
    )
    monkeypatch.setattr(slack, "delete", delete_response)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33", "mention_ts": "123"},
    )

    await slack_notification._delete_notification(notification=notification)

    delete_response.assert_awaited_once()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {
        "channel": None,
        "ts": None,
        "mention_ts": "123",
    }


@pytest.mark.parametrize(
    "alert_status, priority, acknowledge_priority, min_priority_to_mention, expected_result",
    [
        (AlertStatus.solved, 2, 3, 4, False),
        (AlertStatus.active, 3, 2, 4, False),
        (AlertStatus.active, 3, 4, 2, False),
        (AlertStatus.active, 2, 3, 4, True),
    ],
)
async def test_should_have_mention(
    sample_monitor: Monitor,
    alert_status,
    priority,
    acknowledge_priority,
    min_priority_to_mention,
    expected_result,
):
    """'_should_have_mention' should return 'True' if there should be a mention message for the
    notification, otherwise, return 'False'"""
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=min_priority_to_mention,
    )
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
        acknowledged=True,
        priority=priority,
        acknowledge_priority=acknowledge_priority,
    )
    result = slack_notification._should_have_mention(alert, notification_options)
    assert result == expected_result


async def test_send_mention(mocker, monkeypatch, sample_monitor: Monitor):
    """'_send_mention' should send a mention message to the notification message thread"""
    monkeypatch.setattr(slack_mock, "response_ts", "123123")
    slack_send_spy: MagicMock = mocker.spy(slack, "send")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "11.22"},
    )

    await slack_notification._send_mention(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        title="notification title",
        mention="G123456",
    )

    slack_send_spy.assert_called_once_with(
        channel="channel",
        thread_ts="11.22",
        text="<@G123456> Alert *notification title* not acknowledged",
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "11.22", "mention_ts": "123123"}


async def test_send_mention_error(caplog, monkeypatch, sample_monitor: Monitor):
    """'_send_mention' should send a mention message to the notification message thread and log
    an error if it fails"""
    monkeypatch.setattr(slack_mock, "error", "send_error")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "11.22"},
    )

    await slack_notification._send_mention(
        monitor=sample_monitor,
        notification=notification,
        channel="channel",
        title="notification title",
        mention="G123456",
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "11.22"}
    assert_message_in_log(caplog, "Error sending notification mention for")


async def test_delete_mention(mocker, sample_monitor: Monitor):
    """'_delete_mention' should delete a mention message"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": "112233"},
    )

    await slack_notification._delete_mention(notification=notification)

    slack_delete_spy.assert_called_once_with(
        channel="channel",
        ts="112233",
    )

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "33.55", "mention_ts": None}


async def test_delete_mention_no_mention_ts(mocker, sample_monitor: Monitor):
    """'_delete_mention' should just return if the notification doesn't have a mention message"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55"},
    )

    await slack_notification._delete_mention(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "33.55", "mention_ts": None}


async def test_delete_mention_no_notification_data(mocker, sample_monitor: Monitor):
    """'_delete_mention' should just return if the notification data is 'None'"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data=None,
    )

    await slack_notification._delete_mention(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data is None


async def test_delete_mention_none_mention_ts(mocker, sample_monitor: Monitor):
    """'_delete_mention' should just return if the notification doesn't have a mention message"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": None},
    )

    await slack_notification._delete_mention(notification=notification)

    slack_delete_spy.assert_not_called()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"channel": "channel", "ts": "33.55", "mention_ts": None}


async def test_delete_mention_no_channel(mocker, sample_monitor: Monitor):
    """'_delete_mention' should just return if the notification doesn't have a channel"""
    slack_delete_spy: MagicMock = mocker.spy(slack, "delete")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"ts": "33.55", "mention_ts": "112233"},
    )

    await slack_notification._delete_mention(notification=notification)

    slack_delete_spy.assert_not_awaited()

    loaded_notification = await Notification.get_by_id(notification.id)
    assert loaded_notification is not None
    assert loaded_notification.data == {"ts": "33.55", "mention_ts": None}


async def test_notification_mention(mocker, monkeypatch, sample_monitor: Monitor):
    """'notification_mention' should send a mention message if still doesn't have one"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": None},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    send_mention_spy.assert_awaited_once()


async def test_notification_mention_no_mention(mocker, monkeypatch, sample_monitor: Monitor):
    """'notification_mention' should not send a mention message if the 'mention' parameter is not
    set in the notification options"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention=None,
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": None},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_not_called()
    send_mention_spy.assert_not_called()


async def test_notification_mention_no_notification_data(
    mocker, monkeypatch, sample_monitor: Monitor
):
    """'notification_mention' should not send a mention message if the notification data is
    'None'"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data=None,
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_not_called()
    send_mention_spy.assert_not_called()


async def test_notification_mention_notification_no_ts(
    mocker, monkeypatch, sample_monitor: Monitor
):
    """'notification_mention' should not send a mention message if the notification doesn't have the
    'ts' field"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel"},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_not_called()
    send_mention_spy.assert_not_called()


async def test_notification_mention_notification_none_ts(
    mocker, monkeypatch, sample_monitor: Monitor
):
    """'notification_mention' should not send a mention message if the notification doesn't have the
    'ts' field"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": None},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_not_called()
    send_mention_spy.assert_not_called()


async def test_notification_mention_shouldnt_have_mention(
    mocker, monkeypatch, sample_monitor: Monitor
):
    """'notification_mention' should not send a mention message if shouldn't have a mention based
    on the alert and notification options"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: False)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": None},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_awaited_once()
    send_mention_spy.assert_not_called()


async def test_notification_mention_already_sent(mocker, monkeypatch, sample_monitor: Monitor):
    """'notification_mention' should not send a mention message if the notification already has
    a notification mention message"""
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": "11.22"},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_not_called()
    send_mention_spy.assert_not_called()


async def test_notification_mention_mention_on_update(mocker, monkeypatch, sample_monitor: Monitor):
    """'notification_mention' should resend a mention message if the notification already has
    a notification mention message and the option 'mention_on_update' is set to 'True'"""
    monkeypatch.setattr(slack_mock, "response_ts", "123123")
    monkeypatch.setattr(slack_notification, "_should_have_mention", lambda *args: True)
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")
    send_mention_spy: AsyncMock = mocker.spy(slack_notification, "_send_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        mention="mention",
        min_priority_to_mention=5,
        mention_on_update=True,
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "33.55", "mention_ts": "11.22"},
    )

    await slack_notification.notification_mention(
        sample_monitor, alert, notification, notification_options
    )

    delete_mention_spy.assert_awaited_once()
    send_mention_spy.assert_awaited_once()
    await notification.refresh()
    assert notification.data == {"channel": "channel", "ts": "33.55", "mention_ts": "123123"}


async def test_handle_slack_notification_no_alert(mocker):
    """'_handle_slack_notification' should just return if couldn't find an alert with the provided
    id"""
    send_notification_spy: MagicMock = mocker.spy(slack_notification, "send_notification")
    update_notification_spy: MagicMock = mocker.spy(slack_notification, "update_notification")

    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=99999999,
        notification_options=notification_options,
    )

    send_notification_spy.assert_not_called()
    update_notification_spy.assert_not_called()


async def test_handle_slack_notification_min_priority_to_send(mocker, sample_monitor: Monitor):
    """'_handle_slack_notification' should just return if the alert priority is smaller (bigger
    number) than the 'min_priority_to_send' parameter"""
    send_notification_spy: MagicMock = mocker.spy(slack_notification, "send_notification")
    update_notification_spy: MagicMock = mocker.spy(slack_notification, "update_notification")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=4,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    send_notification_spy.assert_not_called()
    update_notification_spy.assert_not_called()


async def test_handle_slack_notification_no_notification_alert_solved(sample_monitor: Monitor):
    """'_handle_slack_notification' should not create a notification if the alert is solved"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
        priority=2,
        solved_at=time_utils.now(),
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    notification = await Notification.get(Notification.alert_id == alert.id)
    assert notification is None


async def test_handle_slack_notification_alert_solved(sample_monitor: Monitor):
    """'_handle_slack_notification' should close the notification if the alert is solved"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=AlertStatus.solved,
        priority=2,
        solved_at=time_utils.now(),
    )
    notification = await Notification.create(
        monitor_id=alert.monitor_id, alert_id=alert.id, target="slack"
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    await notification.refresh()

    assert notification.status == NotificationStatus.closed


async def test_handle_slack_notification_not_solved(sample_monitor: Monitor):
    """'_handle_slack_notification' should keep the notification active if the alert isn't solved"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification = await Notification.create(
        monitor_id=alert.monitor_id, alert_id=alert.id, target="slack"
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    await notification.refresh()

    assert notification.status == NotificationStatus.active


async def test_handle_slack_notification_first_send(mocker, sample_monitor: Monitor):
    """'_handle_slack_notification' should send the notification message if there isn't one yet"""
    send_notification_spy: MagicMock = mocker.spy(slack_notification, "send_notification")
    update_notification_spy: MagicMock = mocker.spy(slack_notification, "update_notification")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    send_notification_spy.assert_called_once()
    update_notification_spy.assert_not_called()


@pytest.mark.parametrize(
    "notification_data",
    [
        {"channel": "channel", "ts": "11.22"},
        {"channel": "channel", "ts": "22.33", "mention_ts": "44.55"},
    ],
)
async def test_handle_slack_notification_update(mocker, sample_monitor: Monitor, notification_data):
    """'_handle_slack_notification' should update the notification message if there one already"""
    send_notification_spy: MagicMock = mocker.spy(slack_notification, "send_notification")
    update_notification_spy: MagicMock = mocker.spy(slack_notification, "update_notification")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    await Notification.create(
        monitor_id=alert.monitor_id, alert_id=alert.id, target="slack", data=notification_data
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    send_notification_spy.assert_not_called()
    update_notification_spy.assert_called_once()


async def test_handle_slack_notification_update_lower_priority(mocker, sample_monitor: Monitor):
    """'_handle_slack_notification' should update an existing notification message even if the alert
    priority is lower (bigger number) than the 'min_priority_to_send' parameter"""
    send_notification_spy: MagicMock = mocker.spy(slack_notification, "send_notification")
    update_notification_spy: MagicMock = mocker.spy(slack_notification, "update_notification")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=4,
    )
    await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "11.22"},
    )
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification._handle_slack_notification(
        alert_id=alert.id,
        notification_options=notification_options,
    )

    send_notification_spy.assert_not_called()
    update_notification_spy.assert_called_once()


@pytest.mark.parametrize("alert_id", [1, 10, 20, 123])
async def test_handle_event(monkeypatch, alert_id):
    """'handle_event' should call '_handle_slack_notification' with the alert id and the
    notification options"""
    handle_slack_notification_mock = AsyncMock()
    monkeypatch.setattr(
        slack_notification, "_handle_slack_notification", handle_slack_notification_mock
    )

    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    await slack_notification.handle_event(
        EventPayload(
            event_source="alert",
            event_source_id=alert_id,
            event_source_monitor_id=0,
            event_name="",
            event_data={},
            extra_payload=None,
        ),
        notification_options,
    )

    handle_slack_notification_mock.assert_awaited_once_with(alert_id, notification_options)


@pytest.mark.parametrize("event_source", ["monitor", "issue", "other"])
async def test_handle_event_invalid_event_source(monkeypatch, event_source):
    """'handle_event' should raise a 'ValueError' exception if the event source is not 'alert'"""
    handle_slack_notification_mock = AsyncMock()
    monkeypatch.setattr(
        slack_notification, "_handle_slack_notification", handle_slack_notification_mock
    )

    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )

    with pytest.raises(ValueError, match=f"Invalid event source '{event_source}'"):
        await slack_notification.handle_event(
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

    handle_slack_notification_mock.assert_not_called()


@pytest.mark.parametrize(
    "notification_data",
    [
        {},
        {"not_ts": "11.22"},
        {"channel": "channel", "ts": "22.33", "mention_ts": "44.55"},
        {"ts": "22.33", "mention_ts": "44.55"},
        {"channel": "channel", "mention_ts": "44.55"},
        {"channel": "channel", "ts": "22.33"},
    ],
)
async def test_clear_slack_notification(mocker, sample_monitor: Monitor, notification_data):
    """'clear_slack_notification' should delete the notification message and mention message"""
    delete_notification_spy: AsyncMock = mocker.spy(slack_notification, "_delete_notification")
    delete_mention_spy: AsyncMock = mocker.spy(slack_notification, "_delete_mention")

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification = await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="slack",
        data=notification_data,
    )

    await slack_notification.clear_slack_notification(notification)

    delete_notification_spy.assert_awaited_once_with(notification)
    delete_mention_spy.assert_awaited_once_with(notification)

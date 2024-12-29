from unittest.mock import AsyncMock

import pytest

import registry as registry
import plugins.slack.actions.actions as actions
import plugins.slack.notifications.slack_notification as slack_notification
from models import Alert, Monitor, Notification, NotificationStatus
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_resend_notification_no_slack_notification_option(
    caplog, monkeypatch, sample_monitor: Monitor
):
    """'_resend_notification' should just return when there is no SlackNotification option"""
    clear_notification_mock = AsyncMock()
    monkeypatch.setattr(slack_notification, "clear_slack_notification", clear_notification_mock)
    slack_notification_mock = AsyncMock()
    monkeypatch.setattr(slack_notification, "slack_notification", slack_notification_mock)
    monkeypatch.setattr(sample_monitor.code, "notification_options", [], raising=False)

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification = await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "123"},
    )

    await actions._resend_notification(notification)

    clear_notification_mock.assert_not_called()
    slack_notification_mock.assert_not_called()
    assert_message_in_log(caplog, f"No 'SlackNotification' option for {sample_monitor}")


async def test_resend_notification(
    mocker, monkeypatch, sample_monitor: Monitor
):
    """'_resend_notification' should clear the notification and send it again"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    clear_notification_mock = AsyncMock()
    monkeypatch.setattr(slack_notification, "clear_slack_notification", clear_notification_mock)
    slack_notification_mock = AsyncMock()
    monkeypatch.setattr(slack_notification, "slack_notification", slack_notification_mock)
    notification_options = slack_notification.SlackNotification(
        channel="channel",
        title="title",
        issues_fields=["col"],
        min_priority_to_send=3,
        mention="mention",
        min_priority_to_mention=2,
    )
    monkeypatch.setattr(
        sample_monitor.code, "notification_options", [notification_options], raising=False
    )

    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification = await Notification.create(
        monitor_id=alert.monitor_id,
        alert_id=alert.id,
        target="slack",
        data={"channel": "channel", "ts": "123"},
    )

    await actions._resend_notification(notification)

    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    clear_notification_mock.assert_awaited_once()
    slack_notification_mock.assert_awaited_once()


async def test_resend_notifications(monkeypatch, sample_monitor: Monitor):
    """'resend_notifications' should clear all notifications for the provided channel and
    update all alerts"""
    resend_notification_mock = AsyncMock()
    monkeypatch.setattr(actions, "_resend_notification", resend_notification_mock)

    alert_test_channel = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification_test_channel = await Notification.create(
        monitor_id=alert_test_channel.monitor_id,
        alert_id=alert_test_channel.id,
        target="slack",
        data={"channel": "test_resend_notification", "ts": "123"},
    )

    alert_other_channel = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="slack",
        data={"channel": "test_resend_notification_other", "ts": "123"},
    )

    await actions.resend_notifications(
        {"slack_channel": "test_resend_notification"}
    )

    assert resend_notification_mock.await_args is not None
    assert resend_notification_mock.await_args[0][0].id == notification_test_channel.id


async def test_resend_notifications_no_notifications_in_channel(
    monkeypatch, sample_monitor: Monitor
):
    """'resend_notifications' should just return when there are no notifications for the
    provided channel"""
    resend_notification_mock = AsyncMock()
    monkeypatch.setattr(actions, "_resend_notification", resend_notification_mock)

    alert_other_channel = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="slack",
        data={"channel": "test_resend_notification_other", "ts": "123"},
    )

    await actions.resend_notifications(
        {"slack_channel": "test_resend_notifications_no_notifications_in_channel"}
    )

    resend_notification_mock.assert_not_called()


async def test_resend_notifications_ignore_other_notifications(
    monkeypatch, sample_monitor: Monitor
):
    """'resend_notifications' should just not resend notifications that are not Slack notifications
    or are not active"""
    resend_notification_mock = AsyncMock()
    monkeypatch.setattr(actions, "_resend_notification", resend_notification_mock)

    alert_other_channel = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="other_target",
        data={"channel": "test_resend_notifications_no_notifications_in_channel", "ts": "123"},
    )
    await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="slack",
        data={"channel": "test_resend_notifications_no_notifications_in_channel", "ts": "123"},
        status=NotificationStatus.closed,
    )

    await actions.resend_notifications(
        {"slack_channel": "test_resend_notifications_no_notifications_in_channel"}
    )

    resend_notification_mock.assert_not_called()

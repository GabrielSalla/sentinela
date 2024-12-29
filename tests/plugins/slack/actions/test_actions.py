from unittest.mock import AsyncMock

import pytest

from plugins.slack.actions import resend_notifications
import registry as registry
from models import Alert, Monitor, Notification

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_resend_notifications(mocker, sample_monitor: Monitor):
    """'resend_notifications' should clear all notifications for the provided channel and
    update all alerts"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    alert_update_spy: AsyncMock = mocker.spy(Alert, "update")

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
    notification_other_channel = await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="slack",
        data={"channel": "test_resend_notification_other", "ts": "123"},
    )

    await resend_notifications(
        {"slack_channel": "test_resend_notification"}
    )

    await notification_test_channel.refresh()
    assert notification_test_channel.data == {"channel": None, "ts": None, "mention_ts": None}

    await notification_other_channel.refresh()
    assert notification_other_channel.data == {
        "channel": "test_resend_notification_other",
        "ts": "123",
    }

    wait_monitor_loaded_spy.assert_awaited_once_with(sample_monitor.id)
    alert_update_spy.assert_awaited_once()
    call_args = alert_update_spy.call_args
    assert call_args[0][0].id == alert_test_channel.id


async def test_resend_notifications_no_notifications_in_channel(
        mocker,
        sample_monitor: Monitor
):
    """'resend_notifications' should just return when there are no notifications for the
    provided channel"""
    wait_monitor_loaded_spy: AsyncMock = mocker.spy(registry, "wait_monitor_loaded")
    alert_update_spy: AsyncMock = mocker.spy(Alert, "update")

    alert_other_channel = await Alert.create(
        monitor_id=sample_monitor.id,
        priority=2,
    )
    notification_other_channel = await Notification.create(
        monitor_id=alert_other_channel.monitor_id,
        alert_id=alert_other_channel.id,
        target="slack",
        data={"channel": "test_resend_notification_other", "ts": "123"},
    )

    await resend_notifications(
        {"slack_channel": "test_resend_notification"}
    )

    await notification_other_channel.refresh()
    assert notification_other_channel.data == {
        "channel": "test_resend_notification_other",
        "ts": "123",
    }

    wait_monitor_loaded_spy.assert_not_called()
    alert_update_spy.assert_not_called()

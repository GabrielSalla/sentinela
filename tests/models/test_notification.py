import logging
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

import utils.time as time_utils
from models import Alert, Monitor, Notification, NotificationStatus
from tests.test_utils import assert_message_in_log

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_close(caplog, mocker, sample_monitor: Monitor):
    """'Notification.close' should close the notification"""
    caplog.set_level(logging.DEBUG)

    alert = await Alert.create(monitor_id=sample_monitor.id)
    notification = await Notification.create(
        monitor_id=sample_monitor.id,
        alert_id=alert.id,
        target="aaa",
    )

    notification_create_event_spy: MagicMock = mocker.spy(notification, "_create_event")

    assert notification.status == NotificationStatus.active
    assert notification.closed_at is None

    await notification.close()

    notification = await Notification.get_by_id(notification.id)

    assert notification.status == NotificationStatus.closed
    assert notification.closed_at > time_utils.now() - timedelta(seconds=1)
    notification_create_event_spy.assert_called_once_with("notification_closed")
    assert_message_in_log(caplog, "Closed")

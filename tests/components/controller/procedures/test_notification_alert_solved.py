from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

import components.controller.procedures.notifications_alert_solved as notifications_alert_solved
from models import Alert, AlertStatus, Monitor, Notification, NotificationStatus
from tests.test_utils import assert_message_in_log, assert_message_not_in_log
from utils.time import now

pytestmark = pytest.mark.asyncio(loop_scope="session")


def get_time(reference: str) -> datetime | None:
    values = {
        "now": now(),
        "ten_seconds_ago": now() - timedelta(seconds=11),
        "five_minutes_ago": now() - timedelta(seconds=301),
    }
    return values.get(reference)


@pytest.mark.parametrize("alert_status", [AlertStatus.active, AlertStatus.solved])
@pytest.mark.parametrize(
    "notification_status", [NotificationStatus.active, NotificationStatus.closed]
)
@pytest.mark.parametrize("alert_solved_at", [None, "now", "five_minutes_ago"])
async def test_notification_alert_solved(
    caplog, sample_monitor: Monitor, monkeypatch, alert_status, notification_status, alert_solved_at
):
    """'_notification_alert_solved' should close notifications that are active but the alert is
    already solved"""
    alert = await Alert.create(
        monitor_id=sample_monitor.id,
        status=alert_status,
        solved_at=get_time(alert_solved_at),  # type:ignore[assignment]
    )
    notification = await Notification.create(
        monitor_id=sample_monitor.id, alert_id=alert.id, target="", status=notification_status
    )

    if alert_status == AlertStatus.active:
        triggered = False
    elif notification_status == NotificationStatus.closed:
        triggered = False
    else:
        triggered = alert_solved_at == "five_minutes_ago"

    await notifications_alert_solved.notifications_alert_solved()

    await notification.refresh()
    if triggered:
        assert notification.status == NotificationStatus.closed
        assert notification.closed_at > now() - timedelta(seconds=1)
        assert_message_in_log(caplog, f"{notification} closed")
    else:
        assert notification.status == notification_status
        assert notification.closed_at is None
        assert_message_not_in_log(caplog, f"{notification} closed")


async def test_notifications_alert_solved_query_result_none(caplog, monkeypatch):
    """'notifications_alert_solved' should log an error if the query result is None"""
    monkeypatch.setattr(
        notifications_alert_solved.databases, "query_application", AsyncMock(return_value=None)
    )

    await notifications_alert_solved.notifications_alert_solved()

    assert_message_in_log(caplog, "Error with query result")


async def test_notifications_alert_solved_monitor_not_found(caplog, monkeypatch):
    """'notifications_alert_solved' should log an error if the notification is not found"""
    monkeypatch.setattr(
        notifications_alert_solved.databases,
        "query_application",
        AsyncMock(return_value=[{"id": 99999999}]),
    )

    await notifications_alert_solved.notifications_alert_solved()

    assert_message_in_log(caplog, "Notification with id '99999999' not found")


async def test_notifications_alert_solved_monitor_not_found_2_results(
    caplog, monkeypatch, sample_monitor: Monitor
):
    """'notifications_alert_solved' should log an error if one notification is not found but should
    continue with the other notifications"""
    alert = await Alert.create(monitor_id=sample_monitor.id, status=AlertStatus.active)
    notification = await Notification.create(
        monitor_id=sample_monitor.id, alert_id=alert.id, target="", status=NotificationStatus.active
    )

    monkeypatch.setattr(
        notifications_alert_solved.databases,
        "query_application",
        AsyncMock(return_value=[{"id": 99999999}, {"id": notification.id}]),
    )

    await notifications_alert_solved.notifications_alert_solved()

    assert_message_in_log(caplog, "Notification with id '99999999' not found")
    assert_message_in_log(caplog, f"{notification} closed")

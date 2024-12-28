import inspect
import re
from unittest.mock import MagicMock

import pytest

import external_requests as external_requests
import services.slack.pattern_match as pattern_match


def test_disable_monitor(mocker):
    """'disable_monitor' should return the coroutine to disable the monitor"""
    disable_monitor_spy: MagicMock = mocker.spy(external_requests, "disable_monitor")

    action = pattern_match.disable_monitor(
        message_match=re.match(r"disable monitor +(\w+)", "disable monitor abc"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    disable_monitor_spy.assert_called_with("abc")

    action.close()


def test_enable_monitor(mocker):
    """'enable_monitor' should return the coroutine to enable the monitor"""
    enable_monitor_spy: MagicMock = mocker.spy(external_requests, "enable_monitor")

    action = pattern_match.enable_monitor(
        message_match=re.match(r"enable monitor +(\w+)", "enable monitor abc"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    enable_monitor_spy.assert_called_with("abc")

    action.close()


def test_alert_acknowledge(mocker):
    """'alert_acknowledge' should return the coroutine to acknowledge the alert"""
    alert_acknowledge_spy: MagicMock = mocker.spy(external_requests, "alert_acknowledge")

    action = pattern_match.alert_acknowledge(
        message_match=re.match(r"ack +(\d+)", "ack 12345"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    alert_acknowledge_spy.assert_called_with(12345)

    action.close()


def test_alert_lock(mocker):
    """'alert_lock' should return the coroutine to lock the alert"""
    alert_lock_spy: MagicMock = mocker.spy(external_requests, "alert_lock")

    action = pattern_match.alert_lock(
        message_match=re.match(r"lock +(\d+)", "lock 12345"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    alert_lock_spy.assert_called_with(12345)

    action.close()


def test_alert_solve(mocker):
    """'alert_solve' should return the coroutine to solve the alert"""
    alert_solve_spy: MagicMock = mocker.spy(external_requests, "alert_solve")

    action = pattern_match.alert_solve(
        message_match=re.match(r"solve +(\d+)", "solve 12345"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    alert_solve_spy.assert_called_with(12345)

    action.close()


def test_issue_drop(mocker):
    """'issue_drop' should return the coroutine to drop the issue"""
    issue_drop_spy: MagicMock = mocker.spy(external_requests, "issue_drop")

    action = pattern_match.issue_drop(
        message_match=re.match(r"drop issue +(\d+)", "drop issue 12345"),
        context={},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    issue_drop_spy.assert_called_with(12345)

    action.close()


def test_resend_slack_notifications(mocker):
    """'resend_slack_notifications' should return the coroutine to resend the slack notifications"""
    resend_slack_notifications_spy: MagicMock = mocker.spy(
        external_requests, "resend_slack_notifications")

    action = pattern_match.resend_slack_notifications(
        message_match=re.match(r"resend notifications", "resend notifications"),
        context={"channel": "C1234567890"},
    )

    assert action is not None
    assert inspect.isawaitable(action)

    resend_slack_notifications_spy.assert_called_with("C1234567890")

    action.close()


@pytest.mark.parametrize(
    "message_user_group",
    [
        "<@aaa>",
        "<@bbb>",
        "<@aaa> ",
        "<@bbb> ",
        "",
        " ",
    ],
)
@pytest.mark.parametrize(
    "message_command, expected_request",
    [
        ("disable monitor abc", "disable_monitor"),
        ("disable monitor   abc", "disable_monitor"),
        ("enable monitor abc", "enable_monitor"),
        ("enable monitor   abc", "enable_monitor"),
        ("ack 12345", "alert_acknowledge"),
        ("ack    12345", "alert_acknowledge"),
        ("lock 12345", "alert_lock"),
        ("lock    12345", "alert_lock"),
        ("solve 12345", "alert_solve"),
        ("solve    12345", "alert_solve"),
        ("drop issue 12345", "issue_drop"),
        ("drop issue    12345", "issue_drop"),
        ("resend notifications", "resend_slack_notifications"),
    ],
)
def test_get_message_reques_match(mocker, message_user_group, message_command, expected_request):
    """'get_message_request' should return the correct request coroutine based on the received
    message"""
    action_spy: MagicMock = mocker.spy(external_requests, expected_request)

    context = {
        "channel": "C1234567890",
    }

    action = pattern_match.get_message_request(message_user_group + message_command, context)

    assert action is not None
    assert inspect.isawaitable(action)

    action_spy.assert_called()

    action.close()


def test_get_message_reques_not_match(mocker):
    """'get_message_request' should return 'None' if the message didn't match with any pattern"""
    result = pattern_match.get_message_request("test 123", {})

    assert result is None

import inspect
import json
import re
from unittest.mock import AsyncMock

import pytest

import commands as commands
import plugins.slack.services.pattern_match as pattern_match
from tests.message_queue.utils import get_queue_items

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_monitor_disable(mocker):
    """'monitor_disable' should return the coroutine to disable the monitor"""
    disable_monitor_spy: AsyncMock = mocker.spy(commands, "monitor_disable")

    match = re.match(r"disable monitor +(\w+)", "disable monitor abc")
    assert match is not None

    action = pattern_match.monitor_disable(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    disable_monitor_spy.assert_called_with("abc")

    action.close()


async def test_monitor_enable(mocker):
    """'monitor_enable' should return the coroutine to enable the monitor"""
    enable_monitor_spy: AsyncMock = mocker.spy(commands, "monitor_enable")

    match = re.match(r"enable monitor +(\w+)", "enable monitor abc")
    assert match is not None

    action = pattern_match.monitor_enable(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    enable_monitor_spy.assert_called_with("abc")

    action.close()


@pytest.mark.parametrize(
    "tasks, expected_tasks",
    [
        ("search", ["search"]),
        ("update", ["update"]),
        ("", ["search", "update"]),
    ],
)
async def test_monitor_refresh(mocker, sample_monitor, tasks, expected_tasks):
    """'monitor_refresh' should refresh monitor tasks and reply in thread"""
    monitor_refresh_spy: AsyncMock = mocker.spy(commands, "monitor_refresh")

    message = f"refresh {sample_monitor.name} {tasks}".strip()
    match = re.match(r"refresh +(\w+)(?: +(search|update))?", message)
    assert match is not None

    await pattern_match.monitor_refresh(
        message_match=match, context={"channel": "C1234567890", "ts": "1234"}
    )

    monitor_refresh_spy.assert_awaited_once_with(sample_monitor.name, expected_tasks)


async def test_alert_acknowledge(mocker):
    """'alert_acknowledge' should return the coroutine to acknowledge the alert"""
    alert_acknowledge_spy: AsyncMock = mocker.spy(commands, "alert_acknowledge")

    match = re.match(r"ack +(\d+)", "ack 12345")
    assert match is not None

    action = pattern_match.alert_acknowledge(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    alert_acknowledge_spy.assert_called_with(12345)

    action.close()


async def test_alert_lock(mocker):
    """'alert_lock' should return the coroutine to lock the alert"""
    alert_lock_spy: AsyncMock = mocker.spy(commands, "alert_lock")

    match = re.match(r"lock +(\d+)", "lock 12345")
    assert match is not None

    action = pattern_match.alert_lock(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    alert_lock_spy.assert_called_with(12345)

    action.close()


async def test_alert_solve(mocker):
    """'alert_solve' should return the coroutine to solve the alert"""
    alert_solve_spy: AsyncMock = mocker.spy(commands, "alert_solve")

    match = re.match(r"solve +(\d+)", "solve 12345")
    assert match is not None

    action = pattern_match.alert_solve(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    alert_solve_spy.assert_called_with(12345)

    action.close()


async def test_issue_drop(mocker):
    """'issue_drop' should return the coroutine to drop the issue"""
    issue_drop_spy: AsyncMock = mocker.spy(commands, "issue_drop")

    match = re.match(r"drop issue +(\d+)", "drop issue 12345")
    assert match is not None

    action = pattern_match.issue_drop(message_match=match, context={})

    assert action is not None
    assert inspect.isawaitable(action)

    issue_drop_spy.assert_called_with(12345)

    action.close()


@pytest.mark.parametrize("slack_channel", ["C1234567890", "C2345678901", "C3456789012"])
async def test_resend_notifications(clear_queue, slack_channel):
    """'resend_notifications' should queue a 'plugin.slack.resend_notifications' action request"""
    match = re.match(r"resend notifications", "resend notifications")
    assert match is not None

    await pattern_match.resend_notifications(
        message_match=match, context={"channel": slack_channel}
    )

    queue_items = get_queue_items()

    assert queue_items == [
        json.dumps(
            {
                "type": "request",
                "payload": {
                    "action": "plugin.slack.resend_notifications",
                    "params": {"slack_channel": slack_channel},
                },
            }
        )
    ]


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
        ("disable monitor abc", "monitor_disable"),
        ("disable monitor   abc", "monitor_disable"),
        ("enable monitor abc", "monitor_enable"),
        ("enable monitor   abc", "monitor_enable"),
        ("ack 12345", "alert_acknowledge"),
        ("ack    12345", "alert_acknowledge"),
        ("lock 12345", "alert_lock"),
        ("lock    12345", "alert_lock"),
        ("solve 12345", "alert_solve"),
        ("solve    12345", "alert_solve"),
        ("drop issue 12345", "issue_drop"),
        ("drop issue    12345", "issue_drop"),
    ],
)
async def test_get_message_request_match_external(
    mocker, message_user_group, message_command, expected_request
):
    """'get_message_request' should return the correct request coroutine based on the received
    message, using the external requests"""
    action_spy: AsyncMock = mocker.spy(commands, expected_request)

    context = {
        "channel": "C1234567890",
    }

    action = pattern_match.get_message_request(message_user_group + message_command, context)

    assert action is not None
    assert inspect.isawaitable(action)

    action_spy.assert_called()

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
        ("resend notifications", "resend_notifications"),
        ("refresh abc", "monitor_refresh"),
        ("refresh abc search", "monitor_refresh"),
        ("refresh abc update", "monitor_refresh"),
    ],
)
async def test_get_message_request_match_plugin(
    mocker, message_user_group, message_command, expected_request
):
    """'get_message_request' should return the correct request coroutine based on the received
    message, using the plugin requests"""
    context = {
        "channel": "C1234567890",
    }

    action = pattern_match.get_message_request(message_user_group + message_command, context)

    assert action is not None
    assert inspect.isawaitable(action)

    action.close()


async def test_get_message_request_not_match(mocker):
    """'get_message_request' should return 'None' if the message didn't match with any pattern"""
    result = pattern_match.get_message_request("test 123", {})

    assert result is None

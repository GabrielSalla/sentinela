from unittest.mock import AsyncMock

import pytest

import external_requests as external_requests
import services.slack.slack as slack
import services.slack.websocket as websocket

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize("message, action_name", [
    ("ack 9999999", "alert_acknowledge"),
    ("lock 9999999", "alert_lock"),
    ("solve 9999999", "alert_solve"),
    ("drop issue 9999999", "issue_drop"),
])
async def test_app_mention(mocker, message, action_name):
    """'app_mention' should call the correct action for the event if there's an action mapped for
    it, reacting to the message with a check mark"""
    action_spy: AsyncMock = mocker.spy(external_requests, action_name)
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")

    body = {
        "event": {"channel": "C12345678", "ts": "1234", "text": message}
    }
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(9999999)
    slack_add_reaction_spy.assert_awaited_once_with(
        channel="C12345678", ts="1234", reaction="ballot_box_with_check"
    )


async def test_app_mention_invalid_action(mocker):
    """'app_mention' should executo no actions if the event doesn't match any message pattern and
    react to the message with an 'x'"""
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")

    body = {
        "event": {"channel": "C12345678", "ts": "1234", "text": "not an action 123"}
    }

    await websocket.app_mention(body)

    slack_add_reaction_spy.assert_awaited_once_with(channel="C12345678", ts="1234", reaction="x")


async def test_app_mention_error(mocker):
    """'app_mention' should react to the message with an 'x' and send the error message if an
    exception is raised"""
    action_spy: AsyncMock = mocker.spy(external_requests, "alert_acknowledge")
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")
    slack_send_spy: AsyncMock = mocker.spy(slack, "send")

    action_spy.side_effect = ValueError("Test error")

    body = {
        "event": {"channel": "C12345678", "ts": "1234", "text": "ack 9999999"}
    }
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(9999999)
    slack_add_reaction_spy.assert_awaited_once_with(channel="C12345678", ts="1234", reaction="x")
    slack_send_spy.assert_awaited_once_with(
        channel="C12345678", thread_ts="1234", text="Test error"
    )


@pytest.mark.parametrize("message, action_name", [
    ("ack 9999999", "alert_acknowledge"),
    ("lock 9999999", "alert_lock"),
    ("solve 9999999", "alert_solve"),
    ("drop issue 9999999", "issue_drop"),
])
async def test_command(mocker, message, action_name):
    """'command' should ack the command and call the correct action for the event if there's an
    action mapped for it"""
    ack_mock = AsyncMock()
    action_spy: AsyncMock = mocker.spy(external_requests, action_name)

    body = {
        "actions": [{"value": message}]
    }
    await websocket.command(ack_mock, body, None)

    ack_mock.assert_awaited_once()
    action_spy.assert_awaited_once_with(9999999)


async def test_command_invalid_action():
    """'command' should ack the command and just return if the event doesn't match any message
    pattern"""
    ack_mock = AsyncMock()

    body = {
        "actions": [{"value": "not an action 123"}]
    }
    await websocket.command(ack_mock, body, None)

    ack_mock.assert_awaited_once()

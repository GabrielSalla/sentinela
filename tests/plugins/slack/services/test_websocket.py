from unittest.mock import AsyncMock

import pytest

import commands as commands
import plugins.slack.services.websocket as websocket
import plugins.slack.slack as slack
from models import Alert, Issue, Monitor

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.parametrize(
    "action_name",
    [
        "alert_acknowledge",
        "alert_lock",
        "alert_solve",
    ],
)
async def test_app_mention_alert_actions(mocker, sample_monitor: Monitor, action_name):
    """'app_mention' should call the correct action for the event if there's an action mapped for
    it, reacting to the message with a check mark"""
    action_spy: AsyncMock = mocker.spy(commands, action_name)
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")

    alert = await Alert.create(monitor_id=sample_monitor.id)
    command_map = {
        "alert_acknowledge": "ack",
        "alert_lock": "lock",
        "alert_solve": "solve",
    }
    message = f"{command_map[action_name]} {alert.id}"

    body = {"event": {"channel": "C12345678", "ts": "1234", "text": message}}
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(alert.id)
    slack_add_reaction_spy.assert_awaited_once_with(
        channel="C12345678", ts="1234", reaction="ballot_box_with_check"
    )


async def test_app_mention_issue_drop(mocker, sample_monitor: Monitor):
    """'app_mention' should execute issue_drop action and react with check mark"""
    action_spy: AsyncMock = mocker.spy(commands, "issue_drop")
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")
    issue = await Issue.create(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})

    body = {"event": {"channel": "C12345678", "ts": "1234", "text": f"drop issue {issue.id}"}}
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(issue.id)
    slack_add_reaction_spy.assert_awaited_once_with(
        channel="C12345678", ts="1234", reaction="ballot_box_with_check"
    )


async def test_app_mention_invalid_action(mocker):
    """'app_mention' should executo no actions if the event doesn't match any message pattern and
    react to the message with an 'x'"""
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")

    body = {"event": {"channel": "C12345678", "ts": "1234", "text": "not an action 123"}}

    await websocket.app_mention(body)

    slack_add_reaction_spy.assert_awaited_once_with(channel="C12345678", ts="1234", reaction="x")


async def test_app_mention_monitor_refresh(mocker, sample_monitor):
    """'app_mention' should refresh monitor tasks and reply in thread"""
    action_spy: AsyncMock = mocker.spy(commands, "monitor_refresh")
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")

    body = {
        "event": {
            "channel": "C12345678",
            "ts": "1234",
            "text": f"refresh {sample_monitor.name}",
        }
    }
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(sample_monitor.name, ["search", "update"])
    slack_add_reaction_spy.assert_awaited_once_with(
        channel="C12345678", ts="1234", reaction="ballot_box_with_check"
    )


async def test_app_mention_error(mocker):
    """'app_mention' should react to the message with an 'x' and send the error message if an
    exception is raised"""
    action_spy: AsyncMock = mocker.spy(commands, "alert_acknowledge")
    slack_add_reaction_spy: AsyncMock = mocker.spy(slack, "add_reaction")
    slack_send_spy: AsyncMock = mocker.spy(slack, "send")

    action_spy.side_effect = ValueError("Test error")

    body = {"event": {"channel": "C12345678", "ts": "1234", "text": "ack 9999999"}}
    await websocket.app_mention(body)

    action_spy.assert_awaited_once_with(9999999)
    slack_add_reaction_spy.assert_awaited_once_with(channel="C12345678", ts="1234", reaction="x")
    slack_send_spy.assert_awaited_once_with(
        channel="C12345678", thread_ts="1234", text="Test error"
    )


@pytest.mark.parametrize(
    "action_name",
    [
        "alert_acknowledge",
        "alert_lock",
        "alert_solve",
        "issue_drop",
    ],
)
async def test_command(mocker, sample_monitor: Monitor, action_name):
    """'command' should ack the command and call the correct action for the event if there's an
    action mapped for it"""
    ack_mock = AsyncMock()
    action_spy: AsyncMock = mocker.spy(commands, action_name)

    if action_name == "issue_drop":
        issue = await Issue.create(monitor_id=sample_monitor.id, model_id="1", data={"id": 1})
        message = f"drop issue {issue.id}"
        expected_id = issue.id
    else:
        alert = await Alert.create(monitor_id=sample_monitor.id)
        command_map = {
            "alert_acknowledge": "ack",
            "alert_lock": "lock",
            "alert_solve": "solve",
        }
        message = f"{command_map[action_name]} {alert.id}"
        expected_id = alert.id

    body = {
        "actions": [{"value": message}],
        "channel": {"id": "C12345678"},
        "message": {"ts": "1234"},
    }
    await websocket.command(ack_mock, body, None)

    ack_mock.assert_awaited_once()
    action_spy.assert_awaited_once_with(expected_id)


async def test_command_invalid_action():
    """'command' should ack the command and just return if the event doesn't match any message
    pattern"""
    ack_mock = AsyncMock()

    body = {
        "actions": [{"value": "not an action 123"}],
        "channel": {"id": "C12345678"},
        "message": {"ts": "1234"},
    }
    await websocket.command(ack_mock, body, None)

    ack_mock.assert_awaited_once()


async def test_command_error(mocker):
    """'command' should send error message if action raises exception"""
    ack_mock = AsyncMock()
    action_spy: AsyncMock = mocker.spy(commands, "alert_acknowledge")
    slack_send_spy: AsyncMock = mocker.spy(slack, "send")

    action_spy.side_effect = ValueError("Test error")

    body = {
        "actions": [{"value": "ack 9999999"}],
        "channel": {"id": "C12345678"},
        "message": {"ts": "1234"},
    }
    await websocket.command(ack_mock, body, None)

    ack_mock.assert_awaited_once()
    action_spy.assert_awaited_once_with(9999999)
    slack_send_spy.assert_awaited_once_with(
        channel="C12345678",
        thread_ts="1234",
        text="Test error",
    )

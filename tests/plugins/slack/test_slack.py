from unittest.mock import MagicMock

import pytest

import plugins.slack.slack as slack

from . import slack_mock

pytestmark = pytest.mark.asyncio(loop_scope="session")

"""As these tests will be using a Slack mock for the responses, they don't test the request's
returned data"""


@pytest.mark.parametrize("text", ["aaa", "bbb", "cccc"])
async def test_get_header_block(text):
    """'get_header_block' should return a header block"""
    result = slack.get_header_block(text)

    assert result["type"] == "header"
    assert result["text"]["text"] == text


@pytest.mark.parametrize(
    "elements_texts",
    [
        ["aaa"],
        ["bbb", "cccc"],
        ["ddd", "eeee", "ff"],
    ],
)
async def test_get_context_block(elements_texts):
    """'get_context_block' should return a context block with the provided list of elements"""
    result = slack.get_context_block(*elements_texts)

    assert result is not None
    assert result["type"] == "context"
    assert len(result["elements"]) == len(elements_texts)
    for element, element_text in zip(result["elements"], elements_texts):
        assert element["text"] == element_text


async def test_get_context_block_empty():
    """'get_context_block' should return 'None' if the list of elements is empty"""
    result = slack.get_context_block()

    assert result is None


@pytest.mark.parametrize("text", ["aaa", "bbb", "cccc"])
async def test_get_section_block(text):
    """'get_section_block' should return a section block"""
    result = slack.get_section_block(text)

    assert result is not None
    assert result["type"] == "section"
    assert result["text"]["text"] == text


async def test_get_section_block_none():
    """'get_section_block' should return 'None' if the list of elements is empty"""
    result = slack.get_section_block(None)

    assert result is None


@pytest.mark.parametrize(
    "buttons",
    [
        [slack.MessageButton(text="text", action_id="action_id", value="value")],
        [
            slack.MessageButton(text="text", action_id="action_id", value="value"),
            slack.MessageButton(text="new text", action_id="new action_id", value="new value"),
        ],
    ],
)
async def test_get_actions_block(buttons):
    """'get_actions_block' should return a context block with the provided list of elements"""
    result = slack.get_actions_block(*buttons)

    assert result is not None
    assert result["type"] == "actions"
    assert len(result["elements"]) == len(buttons)
    for element, buttons_params in zip(result["elements"], buttons):
        assert element["text"]["text"] == buttons_params.text
        assert element["action_id"] == buttons_params.action_id
        assert element["value"] == buttons_params.value


async def test_get_actions_block_empty():
    """'get_actions_block' should return 'None' if the list of elements is empty"""
    result = slack.get_actions_block()

    assert result is None


@pytest.mark.parametrize(
    "kwargs, expected_result",
    [
        (
            {"message_blocks": [{"text": "123"}]},
            [{"blocks": [{"text": "123"}], "color": "#4d4d4d"}],
        ),
        (
            {"message_blocks": [{"text": "123"}], "fallback": None},
            [{"blocks": [{"text": "123"}], "color": "#4d4d4d"}],
        ),
        (
            {"message_blocks": [{"text": "123"}], "fallback": "456"},
            [{"blocks": [{"text": "123"}], "color": "#4d4d4d", "fallback": "456"}],
        ),
        (
            {"message_blocks": [{}], "attachment_color": "color", "fallback": "fallback"},
            [{"blocks": [{}], "color": "color", "fallback": "fallback"}],
        ),
        (
            {"message_blocks": [{"text": "11"}], "attachment_color": "1", "fallback": "22"},
            [{"blocks": [{"text": "11"}], "color": "1", "fallback": "22"}],
        ),
    ],
)
async def test_build_attachments(kwargs, expected_result):
    """'build_attachments' should return an 'attachment' dict, with the provided message blocks,
    color and fallback"""
    result = slack.build_attachments(**kwargs)
    assert result == expected_result


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "channel": "new_channel",
            "text": "another text",
        },
        {
            "channel": "channel",
            "attachments": [],
        },
        {
            "channel": "new_channel",
            "text": "another text",
            "thread_ts": "123456.789",
        },
        {
            "channel": "channel",
            "text": "text",
            "attachments": [],
            "thread_ts": "thread_ts",
        },
        {
            "channel": "new_channel",
            "text": "another text",
            "attachments": [{}],
            "thread_ts": "123456.789",
        },
    ],
)
async def test_send(mocker, kwargs):
    """'send' should send a message to Slack and return it's request response"""
    chat_postmessage_spy: MagicMock = mocker.spy(slack.client, "chat_postMessage")

    result = await slack.send(**kwargs)

    call_args = {**kwargs}
    if "text" not in call_args:
        call_args["text"] = None
    if "attachments" not in call_args:
        call_args["attachments"] = None
    if "thread_ts" not in call_args:
        call_args["thread_ts"] = None

    chat_postmessage_spy.assert_called_once_with(**call_args)

    assert result["ok"] is True
    assert result["channel"] == kwargs["channel"]
    assert result["message"]["ts"] is not None


async def test_send_error(mocker, monkeypatch):
    """'send' should send a message to Slack but return the request response if there's an error"""
    monkeypatch.setattr(slack_mock, "error", "some_error")
    chat_postmessage_spy: MagicMock = mocker.spy(slack.client, "chat_postMessage")

    result = await slack.send(channel="new_channel", text="another text")

    chat_postmessage_spy.assert_called_once()

    assert result["ok"] is False
    assert result["error"] == "some_error"


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "channel": "new_channel",
            "ts": "ts",
            "text": "another text",
        },
        {
            "channel": "channel",
            "ts": "123456.789",
            "attachments": [],
        },
        {
            "channel": "channel",
            "ts": "123456.789",
            "text": "more text",
            "attachments": [],
        },
    ],
)
async def test_update(mocker, kwargs):
    """'update' should update a Slack message with the provided parameters"""
    chat_update_spy: MagicMock = mocker.spy(slack.client, "chat_update")

    result = await slack.update(**kwargs)

    call_args = {**kwargs}
    if "text" not in call_args:
        call_args["text"] = None
    if "attachments" not in call_args:
        call_args["attachments"] = None

    chat_update_spy.assert_called_once_with(**call_args)

    assert result["ok"] is True
    assert result["channel"] == kwargs["channel"]
    assert result["message"]["ts"] is not None


async def test_update_error(mocker, monkeypatch):
    """'update' should update a Slack message but return the request response if there's an error"""
    monkeypatch.setattr(slack_mock, "error", "new_error")
    chat_update_spy: MagicMock = mocker.spy(slack.client, "chat_update")

    result = await slack.update(channel="new_channel", ts="ts", text="another text")

    chat_update_spy.assert_called_once()

    assert result["ok"] is False
    assert result["error"] == "new_error"


async def test_delete(mocker):
    """'delete' should delete a Slack message"""
    chat_delete_spy: MagicMock = mocker.spy(slack.client, "chat_delete")

    result = await slack.delete(channel="channel", ts="ts")

    chat_delete_spy.assert_called_once_with(channel="channel", ts="ts")

    assert result["ok"] is True
    assert result["ts"] is not None


async def test_delete_error(mocker, monkeypatch):
    """'delete' should delete a Slack message but return the request response if there's an error"""
    monkeypatch.setattr(slack_mock, "error", "other_error")
    chat_delete_spy: MagicMock = mocker.spy(slack.client, "chat_delete")

    result = await slack.delete(channel="channel", ts="ts")

    chat_delete_spy.assert_called_once()

    assert result["ok"] is False
    assert result["error"] == "other_error"


async def test_add_reaction(mocker):
    """'add_reaction' should add a reaction to a Slack message"""
    chat_reactions_add_spy: MagicMock = mocker.spy(slack.client, "reactions_add")

    result = await slack.add_reaction(
        channel="channel", ts="ts", reaction="ballot_box_with_check"
    )

    chat_reactions_add_spy.assert_called_once_with(
        channel="channel", timestamp="ts", name="ballot_box_with_check"
    )

    assert result["ok"] is True


async def test_add_reaction_error(mocker, monkeypatch):
    """'add_reaction' should add a reaction to a Slack message but return the request response if
    there's an error"""
    monkeypatch.setattr(slack_mock, "error", "error")
    chat_reactions_add_spy: MagicMock = mocker.spy(slack.client, "reactions_add")

    result = await slack.add_reaction(channel="channel", ts="ts", reaction="reaction")

    chat_reactions_add_spy.assert_called_once_with(
        channel="channel", timestamp="ts", name="reaction"
    )

    assert result["ok"] is False
    assert result["error"] == "error"

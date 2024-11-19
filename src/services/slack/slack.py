import os
from dataclasses import dataclass
from typing import Any, cast

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncSlackResponse, AsyncWebClient

client = AsyncWebClient(token=os.environ["SLACK_TOKEN"])


@dataclass
class MessageButton:
    text: str
    action_id: str
    value: str


def get_header_block(text: str):
    """Build a 'header' block"""
    return {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": text,
            "emoji": True,
        },
    }


def get_context_block(*elements_texts: str) -> dict[str, Any] | None:
    """Build a 'context' block with the provided list of elements"""
    if len(elements_texts) == 0:
        return None

    return {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": element_text,
            }
            for element_text in elements_texts
        ],
    }


def get_section_block(text: str | None) -> dict[str, Any] | None:
    """Build a 'section' block"""
    if text is None:
        return None

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": text,
        },
    }


def get_actions_block(*buttons: MessageButton) -> dict[str, Any] | None:
    """Build a 'actions' block with buttons"""
    if len(buttons) == 0:
        return None

    return {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": button.text},
                "action_id": button.action_id,
                "value": button.value,
            }
            for button in buttons
        ],
    }


def build_attachments(
    message_blocks: list[dict[Any, Any]],
    attachment_color: str = "#4d4d4d",
    fallback: str | None = None,
) -> list[dict[Any, Any]]:
    """Build an 'attachment' dict, with the provided message blocks"""
    attachment = {
        "color": attachment_color,
        "blocks": message_blocks,
    }
    if fallback is not None:
        attachment["fallback"] = fallback

    return [attachment]


async def send(
    channel: str,
    text: str | None = None,
    attachments: list[dict[Any, Any]] | None = None,
    thread_ts: str | None = None,
) -> AsyncSlackResponse:
    """Send a message to a Slack channel with the provided parameters"""
    try:
        return await client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            attachments=attachments,
        )
    except SlackApiError as e:
        return cast(AsyncSlackResponse, e.response)


async def update(
    channel: str,
    ts: str,
    text: str | None = None,
    attachments: list[dict[Any, Any]] | None = None,
) -> AsyncSlackResponse:
    """Update a Slack message with the provided parameters"""
    try:
        return await client.chat_update(
            channel=channel,
            ts=ts,
            text=text,
            attachments=attachments,
        )
    except SlackApiError as e:
        return cast(AsyncSlackResponse, e.response)


async def delete(channel: str, ts: str) -> AsyncSlackResponse:
    """Delete a Slack message"""
    try:
        return await client.chat_delete(
            channel=channel,
            ts=ts,
        )
    except SlackApiError as e:
        return cast(AsyncSlackResponse, e.response)


async def add_reaction(channel: str, ts: str, reaction: str) -> AsyncSlackResponse:
    """Add a reaction to a Slack message"""
    try:
        return await client.reactions_add(
            channel=channel,
            timestamp=ts,
            name=reaction,
        )
    except SlackApiError as e:
        return cast(AsyncSlackResponse, e.response)
